"""Training pipeline: split -> trainer.train -> evaluate -> run directory.

The orchestrator is thin by design; the model families live behind
``BaseTrainer`` in ``classes/``, and their internals (epoch loops,
checkpointing, preprocessing, split protocols) live in ``modules/``.
"""

from .classes.base_trainer import BaseTrainer
from .classes.registry import (
    build_trainer,
    get_trainer_class,
    trainer_class_for_model_type,
)
from .pipeline import TrainingPipeline

__all__ = [
    "BaseTrainer",
    "TrainingPipeline",
    "build_trainer",
    "get_trainer_class",
    "trainer_class_for_model_type",
]
