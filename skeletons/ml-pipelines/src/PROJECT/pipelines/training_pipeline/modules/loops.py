"""The two epoch functions plus batched inference.

The trainer is a thin loop over these; nothing here knows about
checkpoints, schedulers, or config. Two properties are load-bearing:

- **Sample-weighted accumulation.** ``loss.item() * batch_size`` summed
  and divided by the realized sample count, never a mean of per-batch
  means - the latter over-weights a ragged final batch.
- **Injectable metric.** ``metric_fn`` is a parameter, not a hardcoded
  ``torch.max(outputs, 1)`` accuracy. Baking classification accuracy into
  the loop is what forced the "``Const - error``" metric hack in the
  corpus (a regression run reusing a higher-is-better harness).
"""

import logging

import numpy as np
import torch

logger = logging.getLogger(__name__)


def run_one_epoch(
    model,
    loader,
    loss_fn,
    optimizer,
    device,
    metric_fn=None,
    max_batches: int | None = None,
) -> dict:
    """Train for one epoch.

    Args:
        model: Module in (or to be put in) train mode.
        loader: DataLoader yielding ``(inputs, targets)``; ``inputs`` may
            be a tensor or a tuple/list of tensors (multi-input models).
        loss_fn: Callable ``(outputs, targets) -> scalar tensor``.
        optimizer: Torch optimizer already owning ``model``'s parameters.
        device: Target device.
        metric_fn: Optional ``(outputs, targets) -> float``, interpreted
            as a per-sample mean over the batch.
        max_batches: Debug/smoke cap on batches per epoch. For real
            sub-epoch sampling use ``subsample_frac`` in
            :func:`~.datasets.make_loaders`, which draws a *random*
            subset via ``RandomSampler`` - a ``break`` after N batches
            always trains on the same head of the (unshuffled) data.

    Returns:
        ``{"loss": float, "metric": float | None}``.
    """
    model.train()
    total_loss, total_metric, total_count = 0.0, 0.0, 0
    for batch_index, (inputs, targets) in enumerate(loader):
        if max_batches is not None and batch_index >= max_batches:
            break
        inputs = to_device(inputs, device)
        targets = targets.to(device)

        optimizer.zero_grad()
        outputs = model(inputs)
        loss = loss_fn(outputs, targets)
        loss.backward()
        optimizer.step()

        batch_size = targets.size(0)
        total_loss += loss.item() * batch_size
        total_count += batch_size
        if metric_fn is not None:
            total_metric += float(metric_fn(outputs.detach(), targets)) * batch_size

    return _aggregate(total_loss, total_metric, total_count, metric_fn)


@torch.no_grad()
def evaluate(model, loader, loss_fn, device, metric_fn=None) -> dict:
    """Evaluate over a loader with the same averaging contract as training.

    Returns:
        ``{"loss": float, "metric": float | None}`` - identical shape to
        :func:`run_one_epoch` so the trainer can treat both alike.
    """
    model.eval()
    total_loss, total_metric, total_count = 0.0, 0.0, 0
    for inputs, targets in loader:
        inputs = to_device(inputs, device)
        targets = targets.to(device)
        outputs = model(inputs)
        loss = loss_fn(outputs, targets)

        batch_size = targets.size(0)
        total_loss += loss.item() * batch_size
        total_count += batch_size
        if metric_fn is not None:
            total_metric += float(metric_fn(outputs, targets)) * batch_size

    return _aggregate(total_loss, total_metric, total_count, metric_fn)


@torch.no_grad()
def predict(model, loader, device) -> np.ndarray:
    """Batched inference over a loader.

    The loader **must** be built with ``shuffle=False`` and no random
    sampler: the returned array's row order is the loader's iteration
    order, and callers align it positionally with keys/targets. The
    dataset-side helpers in this package default eval loaders to
    ``shuffle=False`` for exactly this reason.

    Args:
        loader: Yields ``inputs`` or ``(inputs, targets)``; targets, if
            present, are ignored.

    Returns:
        Raw model outputs concatenated over batches (no argmax, no
        de-normalisation - those are the caller's decisions).
    """
    model.eval()
    chunks = []
    for batch in loader:
        inputs = batch[0] if isinstance(batch, (tuple, list)) else batch
        outputs = model(to_device(inputs, device))
        chunks.append(outputs.detach().cpu().numpy())
    if not chunks:
        return np.empty((0,))
    return np.concatenate(chunks, axis=0)


def accuracy(outputs, targets) -> float:
    """Multiclass accuracy over one batch - the default ``metric_fn``.

    Lives here as a *provided* metric the caller opts into, never as a
    hardcoded step inside the loops.
    """
    predicted = torch.argmax(outputs, dim=1)
    return (predicted == targets).float().mean().item()


def to_device(inputs, device):
    """Move a tensor, or every tensor in a tuple/list, to ``device``."""
    if isinstance(inputs, (tuple, list)):
        return type(inputs)(item.to(device) for item in inputs)
    return inputs.to(device)


def _aggregate(
    total_loss: float, total_metric: float, total_count: int, metric_fn
) -> dict:
    if total_count == 0:
        raise ValueError("Empty loader: no samples were seen this epoch")
    return {
        "loss": total_loss / total_count,
        "metric": (total_metric / total_count) if metric_fn is not None else None,
    }
