"""Checkpoint schema, DataParallel-safe loading, and transfer loading.

**Never ``torch.save(model, path)``.** A whole-module pickle stores the
class's import path, so the checkpoint dies the moment the module is
renamed or the class moved, and it can execute arbitrary code on load.
The schema here is a plain dict:

``{"model_state_dict", "optimizer_state_dict", "epoch", "metrics"}``

State dicts are stored **unprefixed**: a model trained under
``nn.DataParallel`` carries a ``module.`` prefix on every key, and a
checkpoint that keeps it cannot be loaded into a single-GPU or CPU model
(and vice versa). Saving strips the prefix; loading re-adds it if the
target model is wrapped. Both directions, always.

``early_stopping_pytorch.EarlyStopping`` writes a *bare* state dict to
its ``path``, so :func:`load_checkpoint` accepts both shapes - the best
checkpoint on disk is written by the library, the last one by us.
"""

import logging
from pathlib import Path

import torch

logger = logging.getLogger(__name__)

LAST_CHECKPOINT = "checkpoint_last.pt"
BEST_CHECKPOINT = "checkpoint_best.pt"
_PREFIX = "module."


def save_checkpoint(
    path: str | Path,
    model,
    optimizer=None,
    epoch: int = 0,
    metrics: dict | None = None,
    state_dict: dict | None = None,
) -> Path:
    """Write the checkpoint dict (never a pickled module).

    Args:
        path: Destination ``.pt`` file; parents are created.
        model: Module, possibly ``DataParallel``-wrapped. Its state dict
            is stored unprefixed.
        optimizer: Optional optimizer whose state enables exact resume
            (Adam moments included - resuming without them is a
            different training trajectory).
        epoch: Epoch index this checkpoint represents.
        metrics: The epoch's metric dict, stored for at-a-glance triage.
        state_dict: Optional explicit (unprefixed) state dict to store
            instead of the model's current one - used when the served
            model has been rewound to the best weights but the checkpoint
            must record the final training state.

    Returns:
        The written path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_state_dict": (
            state_dict
            if state_dict is not None
            else strip_module_prefix(_unwrap(model).state_dict())
        ),
        "optimizer_state_dict": optimizer.state_dict() if optimizer is not None else None,
        "epoch": epoch,
        "metrics": metrics or {},
    }
    torch.save(payload, path)
    logger.info("Saved checkpoint (epoch %d) to %s", epoch, path)
    return path


def load_checkpoint(
    path: str | Path,
    model,
    optimizer=None,
    map_location: str | torch.device = "cpu",
    strict: bool = True,
) -> dict:
    """Load a checkpoint into ``model`` (and optionally ``optimizer``).

    Accepts both the dict schema written by :func:`save_checkpoint` and a
    bare ``state_dict`` (what ``EarlyStopping`` writes). ``map_location``
    defaults to CPU so a GPU-trained checkpoint loads on a laptop.

    Returns:
        The checkpoint dict, normalised to the full schema; ``epoch`` is
        ``-1`` and ``metrics`` empty for bare state dicts.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No checkpoint at {path}")
    raw = torch.load(path, map_location=map_location, weights_only=False)
    checkpoint = _normalise(raw)

    state = _match_prefix(checkpoint["model_state_dict"], model)
    model.load_state_dict(state, strict=strict)
    if optimizer is not None and checkpoint["optimizer_state_dict"] is not None:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    logger.info(
        "Loaded checkpoint %s (epoch %s, metrics %s)",
        path,
        checkpoint["epoch"],
        checkpoint["metrics"],
    )
    return checkpoint


def load_partial(
    model,
    ckpt_path: str | Path,
    skip_prefixes: tuple[str, ...] = (),
    strict_shapes: bool = True,
    map_location: str | torch.device = "cpu",
) -> dict:
    """Transfer-learning loader: load what fits, audit what does not.

    Every parameter is reported as ``Imported`` or ``Random
    Initialization`` - without that audit, a silently-skipped backbone
    looks exactly like a successful transfer until the loss curve says
    otherwise.

    Args:
        skip_prefixes: Parameter-name prefixes to leave at their freshly
            initialised values (typically the task head).
        strict_shapes: Skip (rather than attempt) tensors whose shape
            disagrees with the target model. Enabled by default: this is
            what makes the loader usable across a changed head or a
            different class count.

    Returns:
        ``{"imported": [...], "random": [...], "shape_mismatch": [...]}``.
    """
    raw = torch.load(Path(ckpt_path), map_location=map_location, weights_only=False)
    source = strip_module_prefix(_normalise(raw)["model_state_dict"])
    target = _unwrap(model).state_dict()

    to_load, imported, random_init, mismatched = {}, [], [], []
    for name, target_tensor in target.items():
        if any(name.startswith(prefix) for prefix in skip_prefixes):
            random_init.append(name)
            continue
        if name not in source:
            random_init.append(name)
            continue
        if strict_shapes and source[name].shape != target_tensor.shape:
            mismatched.append(name)
            random_init.append(name)
            continue
        to_load[name] = source[name]
        imported.append(name)

    target.update(to_load)
    _unwrap(model).load_state_dict(target)

    for name in imported:
        logger.info("%-48s Imported", name)
    for name in random_init:
        reason = "shape mismatch" if name in mismatched else "not in checkpoint / skipped"
        logger.info("%-48s Random Initialization (%s)", name, reason)
    logger.info(
        "Transfer load from %s: %d imported, %d random-init (%d shape mismatches)",
        ckpt_path,
        len(imported),
        len(random_init),
        len(mismatched),
    )
    return {"imported": imported, "random": random_init, "shape_mismatch": mismatched}


def resume(run_dir: str | Path, mode: str = "continue") -> Path:
    """Resolve which checkpoint a resume should load.

    Args:
        mode: ``"continue"`` picks the last checkpoint (keep training the
            trajectory that was interrupted); ``"from_best"`` picks the
            best-monitored checkpoint (rewind and branch from the best
            point). They are different products, so the choice is named
            in config rather than implied.

    Raises:
        ValueError: On an unknown mode.
        FileNotFoundError: If the requested checkpoint is absent.
    """
    if mode not in ("continue", "from_best"):
        raise ValueError(f"resume mode must be 'continue' or 'from_best', got {mode!r}")
    filename = LAST_CHECKPOINT if mode == "continue" else BEST_CHECKPOINT
    path = Path(run_dir) / filename
    if not path.exists():
        raise FileNotFoundError(
            f"resume(mode={mode!r}) wants {path}, which does not exist"
        )
    logger.info("Resuming (%s) from %s", mode, path)
    return path


def strip_module_prefix(state: dict) -> dict:
    """Drop the ``module.`` prefix ``DataParallel`` adds to every key."""
    return {
        (k[len(_PREFIX) :] if k.startswith(_PREFIX) else k): v for k, v in state.items()
    }


def add_module_prefix(state: dict) -> dict:
    """Add the ``module.`` prefix for loading into a wrapped model."""
    return {(k if k.startswith(_PREFIX) else _PREFIX + k): v for k, v in state.items()}


def _match_prefix(state: dict, model) -> dict:
    """Align a state dict's prefixing with the target model's wrapping."""
    wrapped = _is_wrapped(model)
    state = strip_module_prefix(state)
    return add_module_prefix(state) if wrapped else state


def _is_wrapped(model) -> bool:
    from torch import nn

    return isinstance(model, (nn.DataParallel, nn.parallel.DistributedDataParallel))


def _unwrap(model):
    return model.module if _is_wrapped(model) else model


def _normalise(raw) -> dict:
    """Coerce a loaded object into the full checkpoint schema."""
    from torch import nn

    if isinstance(raw, nn.Module):
        # A whole-module pickle. Loadable only while its defining module
        # keeps its import path, which is why this package never writes one.
        raise TypeError(
            "Checkpoint is a pickled nn.Module, not a state dict. Re-export it "
            "with save_checkpoint(path, loaded_module) before using it here."
        )
    if isinstance(raw, dict) and "model_state_dict" in raw:
        return {
            "model_state_dict": raw["model_state_dict"],
            "optimizer_state_dict": raw.get("optimizer_state_dict"),
            "epoch": raw.get("epoch", -1),
            "metrics": raw.get("metrics", {}),
        }
    # Bare state dict (EarlyStopping's best file, or a third-party export).
    return {
        "model_state_dict": raw,
        "optimizer_state_dict": None,
        "epoch": -1,
        "metrics": {},
    }
