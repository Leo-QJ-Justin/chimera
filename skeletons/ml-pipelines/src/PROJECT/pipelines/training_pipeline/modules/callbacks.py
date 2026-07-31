"""Epoch-boundary callbacks: early stopping, NaN guard, LR schedule.

Thin wiring only - none of this owns training state:

- **Early stopping** is ``early_stopping_pytorch.EarlyStopping``, not a
  hand-rolled patience counter. The library tracks patience *and*
  persists the best ``state_dict`` on every improvement, so early
  stopping and best-checkpointing are one object. It is hardwired to
  lower-is-better, so :class:`EarlyStoppingMonitor` negates the value for
  ``mode="max"`` - the ``monitor: {name, mode}`` config choice is
  honoured here instead of by inventing ``Const - error`` metrics.
- **NaN guard**: a diverged epoch must not overwrite a good checkpoint,
  and repeated NaNs should end the run rather than burn the remaining
  epochs.
- **LR**: ``ReduceLROnPlateau`` on the same monitored value the early
  stopper sees. Plateau-driven beats StepLR's fixed calendar, which
  decays on schedule whether or not the loss has stalled.
"""

import logging
import math
from pathlib import Path

from early_stopping_pytorch import EarlyStopping
from torch.optim.lr_scheduler import ReduceLROnPlateau

from .checkpointing import BEST_CHECKPOINT

logger = logging.getLogger(__name__)


class EarlyStoppingMonitor:
    """``EarlyStopping`` adapted to a ``monitor: {name, mode}`` contract.

    Args:
        patience: Epochs without improvement before stopping.
        run_dir: Best checkpoint is written to
            ``run_dir/checkpoint_best.pt`` (a bare ``state_dict``; see
            ``checkpointing.load_checkpoint``, which accepts both shapes).
        mode: ``"min"`` (loss-like) or ``"max"`` (score-like).
        delta: Minimum change that counts as an improvement.

    Attributes:
        early_stop: True once patience is exhausted.
        best_path: Path of the best checkpoint on disk.
        best_value: Best monitored value seen, in the caller's sign.
    """

    def __init__(
        self,
        patience: int,
        run_dir: str | Path,
        mode: str = "min",
        delta: float = 0.0,
        trace_func=None,
    ):
        if mode not in ("min", "max"):
            raise ValueError(f"monitor mode must be 'min' or 'max', got {mode!r}")
        self.mode = mode
        self.best_path = Path(run_dir) / BEST_CHECKPOINT
        self._stopper = EarlyStopping(
            patience=patience,
            verbose=True,
            delta=delta,
            path=str(self.best_path),
            # Route the library's traces into the run's log file rather
            # than stdout, where they would be lost.
            trace_func=trace_func or logger.info,
        )

    def __call__(self, value: float, model) -> bool:
        """Record an epoch's monitored value; save on improvement.

        Returns:
            True if training should stop now.
        """
        self._stopper(self._signed(value), model)
        return self._stopper.early_stop

    @property
    def early_stop(self) -> bool:
        return self._stopper.early_stop

    @property
    def counter(self) -> int:
        return self._stopper.counter

    @property
    def best_value(self) -> float | None:
        best = self._stopper.best_val_loss
        return None if best is None else self._signed(best)

    def _signed(self, value: float) -> float:
        """Negate for ``max`` mode; the library only knows lower-is-better."""
        return -value if self.mode == "max" else value


class NaNGuard:
    """Stop the run on non-finite losses, and never checkpoint one.

    A NaN epoch is not a slightly worse epoch: its weights are garbage,
    and letting it reach the checkpointer destroys the best model on
    disk. One NaN is tolerated (it can be a bad batch); consecutive NaNs
    end the run.

    Attributes:
        consecutive: Current consecutive non-finite count.
        should_stop: True once ``max_consecutive`` is reached.
    """

    def __init__(self, max_consecutive: int = 2):
        self.max_consecutive = max_consecutive
        self.consecutive = 0
        self.should_stop = False

    def check(self, value: float) -> bool:
        """Return True when the epoch is healthy (finite)."""
        if value is None or math.isnan(value) or math.isinf(value):
            self.consecutive += 1
            self.should_stop = self.consecutive >= self.max_consecutive
            logger.warning(
                "Non-finite monitored value (%s); skipping checkpoint "
                "(%d/%d consecutive)",
                value,
                self.consecutive,
                self.max_consecutive,
            )
            return False
        self.consecutive = 0
        return True


def make_scheduler(
    optimizer,
    mode: str = "min",
    factor: float = 0.5,
    patience: int = 2,
    min_lr: float = 1e-6,
) -> ReduceLROnPlateau:
    """Build the plateau LR scheduler for the monitored metric.

    ``mode`` must match the monitor's mode; the scheduler steps on the
    same value the early stopper sees, so the two never disagree about
    what "better" means.
    """
    return ReduceLROnPlateau(
        optimizer, mode=mode, factor=factor, patience=patience, min_lr=min_lr
    )


def current_lr(optimizer) -> float:
    """First param group's LR - logged per epoch so decays are visible.

    ``ReduceLROnPlateau`` dropped its ``verbose`` argument in recent
    torch, so the decay is only observable if the caller records the LR
    as a metric.
    """
    return float(optimizer.param_groups[0]["lr"])
