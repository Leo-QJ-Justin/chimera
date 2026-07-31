"""Trainers: one class per model family, all behind ``BaseTrainer``.

``trainer.kind`` **is** the family - the same string names the config
group file, the class below, and ``model_type`` in ``metadata.json``.
Two call sites use this table: the training pipeline builds a trainer from
config, the inference pipeline resolves one from a saved run's
``model_type``. One dict, so "which families exist" cannot drift into two
``if`` chains.

**Imports are lazy on purpose.** LightGBM, XGBoost and torch are optional
extras; importing them here would make ``import training_pipeline`` fail on
a machine that only runs the sklearn families. The import happens when the
family is asked for, and the guarded import inside each module turns a
missing extra into a sentence naming the install.
"""

import importlib
import logging

from .base_trainer import BaseTrainer

logger = logging.getLogger(__name__)

# kind -> (module, class name). Data, not imports: see the module docstring.
TRAINERS = {
    "logreg": ("logreg_trainer", "LogisticRegressionTrainer"),
    "random_forest": ("random_forest_trainer", "RandomForestTrainer"),
    "lightgbm": ("lightgbm_trainer", "LightGBMTrainer"),
    "xgboost": ("xgboost_trainer", "XGBoostTrainer"),
    "torch": ("torch_trainer", "TorchTrainer"),
}

# Per-family harness sections: TrainerConfig -> the family's own kwargs.
# Only the selected family's section is passed on, so an unused section can
# stay in the schema without every trainer having to accept it.
_HARNESS = {
    "lightgbm": lambda cfg: cfg.lightgbm.model_dump(),
    "xgboost": lambda cfg: cfg.xgboost.model_dump(),
    "torch": lambda cfg: {"options": cfg.torch.model_dump()},
}


def get_trainer_class(kind: str) -> type[BaseTrainer]:
    """The trainer class for a family key (config ``kind``, or ``model_type``).

    Raises:
        KeyError: On an unknown family, listing what is registered.
    """
    if kind not in TRAINERS:
        raise KeyError(
            f"Unknown trainer {kind!r}; registered: {sorted(TRAINERS)}. Add an "
            "entry to TRAINERS and a configs/trainer/<kind>.yaml declaring it."
        )
    module, class_name = TRAINERS[kind]
    return getattr(importlib.import_module(f".{module}", __package__), class_name)


def build_trainer(
    trainer_cfg,
    *,
    task: str = "classification",
    seed: int = 42,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    cv_mode: str = "stratified",
) -> BaseTrainer:
    """Construct the configured trainer.

    Args:
        trainer_cfg: The ``trainer`` section (a
            :class:`~PROJECT.schemas.TrainerConfig`): which family, its
            params, and that family's harness knobs.
        task: Run-level task; a trainer never guesses it from the labels.
        seed: The single run seed.
        numeric_features: Numeric feature columns, in contract order.
        categorical_features: Categorical feature columns, in contract order.
        cv_mode: The run's ``split.mode``, which picks the CV splitter (D9).

    Returns:
        An unfitted :class:`BaseTrainer`.
    """
    trainer_cls = get_trainer_class(trainer_cfg.kind)
    harness = _HARNESS.get(trainer_cfg.kind, lambda _: {})(trainer_cfg)
    trainer = trainer_cls(
        dict(trainer_cfg.params),
        task=task,
        seed=seed,
        numeric_features=list(numeric_features or []),
        categorical_features=list(categorical_features or []),
        cv_mode=cv_mode,
        **harness,
    )
    logger.info("Built trainer %s (task=%s)", trainer.model_type, task)
    return trainer


__all__ = ["TRAINERS", "BaseTrainer", "build_trainer", "get_trainer_class"]
