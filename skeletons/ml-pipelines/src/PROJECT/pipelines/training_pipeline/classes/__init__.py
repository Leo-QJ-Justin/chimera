"""Trainers: one class per model family, all behind ``BaseTrainer``.

Concrete trainers are imported lazily through ``registry`` so that an
optional extra (lightgbm, torch) is only imported when it is selected.
"""

from .base_trainer import BaseTrainer
from .registry import build_trainer, get_trainer_class, trainer_class_for_model_type

__all__ = [
    "BaseTrainer",
    "build_trainer",
    "get_trainer_class",
    "trainer_class_for_model_type",
]
