"""Datasets, loaders, and the feature-block registry.

The registry replaces the magic-slice idiom
(``features[43:91] / 1600``): blocks are declared once as
``(name, width, scale)``, offsets are *derived*, and the total width
becomes a computed invariant that a config typo trips immediately
instead of at epoch 3. ``to_manifest()`` is written into the run
directory so a saved model's input layout is recoverable from artifacts
alone.

Loader construction centralises three things that are easy to get wrong
independently: seeded shuffling (generator + ``worker_init_fn`` from
``core.seeding``), ``shuffle=False`` on every evaluation loader so
predictions stay positionally alignable, and sub-epoch subsampling via
``RandomSampler`` rather than a ``break`` after N batches.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, RandomSampler, Subset

from ....core.seeding import torch_generator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureBlock:
    """One contiguous block of an assembled feature vector.

    Args:
        name: Block name, unique within a registry.
        width: Number of columns the block occupies.
        scale: Divisor applied to the block. Fixed physical divisors
            (1600 W/m2, 100 percent, 255) beat fitted scalers for
            physically-bounded feeds: nothing to persist, so train/serve
            skew is impossible by construction.
        source: Upstream feed/table the block came from (audit only).
        dtype: Declared dtype for the block (audit only).
    """

    name: str
    width: int
    scale: float = 1.0
    source: str | None = None
    dtype: str = "float32"


@dataclass
class FeatureBlockRegistry:
    """Ordered feature blocks with derived offsets and a width invariant."""

    blocks: list[FeatureBlock] = field(default_factory=list)

    def __post_init__(self):
        names = [b.name for b in self.blocks]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"Duplicate feature block names: {sorted(duplicates)}")
        if any(b.width <= 0 for b in self.blocks):
            raise ValueError("Every feature block needs a positive width")

    @property
    def total_width(self) -> int:
        """The invariant that replaces the hand-typed vector length."""
        return sum(b.width for b in self.blocks)

    def offsets(self) -> dict[str, tuple[int, int]]:
        """Block name -> ``(start, stop)``, derived from the declared order."""
        out, cursor = {}, 0
        for block in self.blocks:
            out[block.name] = (cursor, cursor + block.width)
            cursor += block.width
        return out

    def slice_of(self, name: str) -> slice:
        """The ``slice`` covering one named block."""
        start, stop = self.offsets()[name]
        return slice(start, stop)

    def assert_width(self, actual_width: int) -> None:
        """Raise if an assembled array disagrees with the declared blocks.

        Raises:
            ValueError: With the per-block breakdown, which is what makes
                "expected 133, got 121" diagnosable.
        """
        if actual_width != self.total_width:
            raise ValueError(
                f"Feature width mismatch: array has {actual_width} columns, "
                f"blocks declare {self.total_width} "
                f"({ {b.name: b.width for b in self.blocks} })"
            )

    def apply_scaling(self, array: np.ndarray) -> np.ndarray:
        """Divide each block by its declared scale (no fitted state)."""
        self.assert_width(array.shape[-1])
        out = np.asarray(array, dtype=np.float32).copy()
        offsets = self.offsets()
        for block in self.blocks:
            if block.scale != 1.0:
                start, stop = offsets[block.name]
                out[..., start:stop] /= block.scale
        return out

    def to_manifest(self) -> dict:
        """The loggable feature contract: name, slice, source, dtype, scale."""
        offsets = self.offsets()
        return {
            "total_width": self.total_width,
            "blocks": [
                {
                    "name": b.name,
                    "start": offsets[b.name][0],
                    "stop": offsets[b.name][1],
                    "width": b.width,
                    "scale": b.scale,
                    "source": b.source,
                    "dtype": b.dtype,
                }
                for b in self.blocks
            ],
        }

    @classmethod
    def from_config(cls, blocks) -> "FeatureBlockRegistry":
        """Build from a list of mappings in config (Hydra/YAML friendly)."""
        return cls([FeatureBlock(**dict(b)) for b in blocks])


class TabularTensorDataset(Dataset):
    """Minimal in-memory tabular dataset with constructor validation.

    Validation happens in ``__init__``, before any training starts: a
    shape mismatch should fail at construction, not at epoch 3.

    Args:
        X: 2-D features, shape ``(n_samples, n_features)``.
        y: 1-D targets, length ``n_samples``.
        target_dtype: ``"long"`` for classification targets (what
            ``CrossEntropyLoss`` requires), ``"float"`` for regression.
    """

    def __init__(self, X, y, target_dtype: str = "long"):
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        if X.ndim != 2:
            raise ValueError(
                f"X must be 2-D (n_samples, n_features), got shape {X.shape}"
            )
        if len(X) != len(y):
            raise ValueError(f"X has {len(X)} rows but y has {len(y)}")
        if len(X) == 0:
            raise ValueError("Empty dataset")
        if target_dtype not in ("long", "float"):
            raise ValueError(
                f"target_dtype must be 'long' or 'float', got {target_dtype!r}"
            )

        self.X = torch.from_numpy(X)
        self.y = (
            torch.from_numpy(y.astype(np.int64))
            if target_dtype == "long"
            else torch.from_numpy(y.astype(np.float32))
        )
        self.n_features = X.shape[1]

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, index):
        return self.X[index], self.y[index]


def make_loaders(
    dataset: Dataset,
    splits: dict[str, list[int]],
    batch_size: int,
    num_workers: int = 0,
    pin_memory: bool = False,
    seed: int = 42,
    subsample_frac: float = 1.0,
    train_split: str = "train",
    drop_last: str | bool = "auto",
) -> dict[str, DataLoader]:
    """Build one DataLoader per split from positional indices.

    Args:
        splits: Split name -> positional indices into ``dataset``. The
            *durable* split record is ``core.splits`` membership by
            stable key; these positions are derived from it per run.
        subsample_frac: Fraction of the training split drawn per epoch,
            via ``RandomSampler(num_samples=...)``. The sampler form
            re-draws every epoch; a ``break`` after N batches would train
            on the same head of the data forever.
        drop_last: ``"auto"`` drops the final training batch only when it
            would hold a single sample, because ``BatchNorm1d`` raises on
            a batch of one in train mode. ``True``/``False`` force the
            behaviour.

    Returns:
        Split name -> DataLoader. Only ``train_split`` is shuffled;
        every other loader keeps dataset order so predictions stay
        positionally alignable with keys and targets.
    """
    generator, worker_init_fn = torch_generator(seed)
    loaders: dict[str, DataLoader] = {}
    for name, indices in splits.items():
        subset = Subset(dataset, list(indices))
        is_train = name == train_split
        sampler = None
        shuffle = is_train
        if is_train and subsample_frac < 1.0:
            num_samples = max(1, int(len(subset) * subsample_frac))
            # Sampler and shuffle are mutually exclusive; RandomSampler
            # already shuffles what it draws.
            sampler = RandomSampler(
                subset, replacement=False, num_samples=num_samples, generator=generator
            )
            shuffle = False
            logger.info(
                "Split %r sub-epoch sampling: %d of %d samples per epoch",
                name,
                num_samples,
                len(subset),
            )
        loaders[name] = DataLoader(
            subset,
            batch_size=batch_size,
            shuffle=shuffle,
            sampler=sampler,
            num_workers=num_workers,
            pin_memory=pin_memory,
            generator=generator,
            worker_init_fn=worker_init_fn if num_workers > 0 else None,
            drop_last=_resolve_drop_last(drop_last, is_train, len(subset), batch_size),
        )
        logger.info("Loader %r: %d samples, batch_size=%d", name, len(subset), batch_size)
    return loaders


def _resolve_drop_last(
    drop_last: str | bool, is_train: bool, n: int, batch_size: int
) -> bool:
    if drop_last != "auto":
        return bool(drop_last)
    return is_train and n % batch_size == 1
