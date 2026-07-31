"""Trainer registry: config -> a ``BaseTrainer``, and nothing else.

Two call sites, one table. The training pipeline builds a trainer from
the ``trainer/`` config group; the inference pipeline resolves the class
from ``metadata.json``'s ``model_type`` and calls its ``load``. Both go
through here, so "which families exist" is one dict rather than two
drifting ``if`` chains.

**Imports are lazy on purpose.** LightGBM and torch are optional extras;
importing them at module import would make ``import
PROJECT.pipelines.training_pipeline`` fail on a machine that only ever
runs the sklearn trainer. The import happens when the trainer is asked
for, and the guarded import inside each module turns a missing extra into
a sentence naming the install.
"""

import logging

logger = logging.getLogger(__name__)


def _sklearn():
    from .sklearn_trainer import SklearnTrainer

    return SklearnTrainer


def _lightgbm():
    from .lightgbm_trainer import LightGBMTrainer

    return LightGBMTrainer


def _torch():
    from .torch_trainer import TorchTrainer

    return TorchTrainer


TRAINERS = {
    "sklearn": _sklearn,
    "lightgbm": _lightgbm,
    "torch": _torch,
}


def get_trainer_class(kind: str):
    """The trainer class registered under ``kind``.

    Raises:
        KeyError: On an unknown kind, listing what is registered.
    """
    if kind not in TRAINERS:
        raise KeyError(
            f"Unknown trainer {kind!r}; registered: {sorted(TRAINERS)}. Add a "
            "loader to TRAINERS and a configs/trainer/<name>.yaml declaring it."
        )
    return TRAINERS[kind]()


def trainer_class_for_model_type(model_type: str):
    """Resolve ``metadata.json``'s ``model_type`` to its trainer class.

    ``model_type`` is ``"<kind>:<name>"``. Splitting on the prefix rather
    than storing a class path means a renamed module never orphans a saved
    run.
    """
    kind = str(model_type).split(":", 1)[0]
    return get_trainer_class(kind)


def build_trainer(
    trainer_cfg,
    *,
    task: str = "classification",
    seed: int = 42,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    cv_mode: str = "stratified",
):
    """Construct the configured trainer.

    Args:
        trainer_cfg: The ``trainer`` section (a
            :class:`~PROJECT.schemas.TrainerConfig`): which family, which
            estimator, its params, and that family's harness knobs.
        task: Run-level task; a trainer never guesses it from the labels.
        seed: The single run seed.
        numeric_features: Numeric feature columns, in contract order.
        categorical_features: Categorical feature columns, in contract order.
        cv_mode: The run's ``split.mode``, which picks the CV splitter (D9).

    Returns:
        An unfitted :class:`BaseTrainer`.
    """
    trainer_cls = get_trainer_class(trainer_cfg.kind)
    shared = {
        "task": task,
        "seed": seed,
        "numeric_features": list(numeric_features or []),
        "categorical_features": list(categorical_features or []),
        "cv_mode": cv_mode,
    }
    # Only the selected family's harness section is passed on; the others
    # exist in the schema so an unused section never has to be deleted.
    if trainer_cfg.kind == "torch":
        extra = {"options": trainer_cfg.torch.model_dump()}
    elif trainer_cfg.kind == "lightgbm":
        extra = trainer_cfg.lightgbm.model_dump()
    else:
        extra = {}

    trainer = trainer_cls(trainer_cfg.name, dict(trainer_cfg.params), **shared, **extra)
    logger.info("Built trainer %s (task=%s)", trainer.model_type, task)
    return trainer
