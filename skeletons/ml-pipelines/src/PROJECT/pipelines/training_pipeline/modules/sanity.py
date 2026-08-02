"""The overfit-single-batch sanity check.

The cheapest architecture bug detector available: a model that cannot
drive one batch to a near-perfect fit has a wiring problem (wrong loss,
frozen parameters, detached graph, LR of zero), and no amount of epochs on
the full dataset will fix it. It runs in seconds, before the real training.

It builds its **own** model, optimizer and loss internally: the check
must not leave the training model or optimizer polluted with 100 steps
of single-batch gradient, which is exactly what makes it safe to run
unconditionally at the start of a run.
"""

import logging

import torch
from torch import nn

from .loops import to_device

logger = logging.getLogger(__name__)


def overfit_single_batch(
    model_factory,
    loader,
    device,
    num_iterations: int = 100,
    threshold: float = 0.95,
    metric_fn=None,
    loss_fn=None,
    lr: float = 1e-3,
    loss_ratio: float = 0.1,
) -> bool:
    """Try to overfit one batch; log and return the verdict.

    Args:
        model_factory: Zero-argument callable returning a **fresh**
            model. A factory, not an instance, so the check cannot leak
            its gradients into the run's model.
        loader: Any training loader; its first batch is used.
        device: Device from ``device.setup_device``.
        num_iterations: Gradient steps on that one batch.
        threshold: Pass mark for ``metric_fn`` (e.g. accuracy >= 0.95).
        metric_fn: ``(outputs, targets) -> float``. When None, the
            verdict falls back to the loss criterion below.
        loss_fn: Defaults to ``CrossEntropyLoss`` (classification). Pass
            e.g. ``nn.MSELoss()`` for regression.
        lr: Adam LR for the check only.
        loss_ratio: Used when ``metric_fn`` is None - the final loss must
            fall to this fraction of the initial loss.

    Returns:
        True if the model overfit the batch.
    """
    model = model_factory().to(device)
    model.train()
    loss_fn = loss_fn or nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    inputs, targets = next(iter(loader))
    inputs = to_device(inputs, device)
    targets = targets.to(device)

    initial_loss, final_loss, final_metric = None, None, None
    for iteration in range(num_iterations):
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = loss_fn(outputs, targets)
        loss.backward()
        optimizer.step()

        final_loss = loss.item()
        initial_loss = final_loss if initial_loss is None else initial_loss
        if metric_fn is not None:
            final_metric = float(metric_fn(outputs.detach(), targets))
        if iteration % 20 == 0:
            logger.info(
                "Sanity iter %3d: loss %.6f%s",
                iteration,
                final_loss,
                "" if final_metric is None else f", metric {final_metric:.4f}",
            )

    if metric_fn is not None:
        passed = final_metric >= threshold
        detail = f"metric {final_metric:.4f} vs threshold {threshold}"
    else:
        passed = final_loss <= initial_loss * loss_ratio
        detail = f"loss {initial_loss:.6f} -> {final_loss:.6f} (need <= x{loss_ratio})"

    if passed:
        logger.info("Sanity check PASSED: model can overfit a single batch (%s)", detail)
    else:
        logger.warning(
            "Sanity check FAILED: model cannot overfit a single batch (%s) - "
            "check architecture, loss, LR, and that gradients reach every layer",
            detail,
        )
    return passed
