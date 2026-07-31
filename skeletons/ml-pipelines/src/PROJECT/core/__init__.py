"""Framework-agnostic core utilities shared by every pipeline.

Pipelines import from this package; they never copy its code. Optional
heavy dependencies (mlflow, torch, omegaconf, matplotlib) degrade
gracefully when absent - see each module's header.
"""

from .seeding import set_seed
from .timing import stage_timer

__all__ = ["set_seed", "stage_timer"]
