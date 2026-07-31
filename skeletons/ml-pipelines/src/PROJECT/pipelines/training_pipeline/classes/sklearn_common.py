"""Shared plumbing for trainers whose artifact is one sklearn ``Pipeline``.

Shared *plumbing*, never shared *identity*: every family still brings its
own class, its own ``_build_model`` and its own search space. What lives
here is only the mechanics that would otherwise be copied verbatim -
assembling the fitted preprocessor and estimator into a single
``Pipeline``, predicting through it, and the joblib save/load pair.

Why one ``Pipeline`` is the artifact (D6): ``joblib.dump`` captures
preprocessing and model *together*, so they cannot drift apart at serving
time, and per-fold refitting under ``cross_validate``/Optuna is automatic
rather than remembered.

Two levels, because the boosters differ where it matters:

- :class:`PipelineArtifactTrainer` - artifact mechanics only. LightGBM and
  XGBoost use it and write their own ``train`` (their early stopping needs
  the *transformed* validation matrix, which a ``Pipeline.fit`` signature
  cannot carry).
- :class:`SklearnEstimatorTrainer` - adds the plain one-shot fit and
  ``mlflow.sklearn`` logging. Logistic regression and random forest use it.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ..modules.model_logging import log_flavor_model
from .base_trainer import BaseTrainer

logger = logging.getLogger(__name__)

MODEL_FILENAME = "model.joblib"


class PipelineArtifactTrainer(BaseTrainer):
    """One ``Pipeline(preprocess, model)`` on disk, however it was fitted."""

    def assemble(self, preprocessor, model) -> None:
        """Store two already-fitted halves as the artifact.

        Constructing a ``Pipeline`` does not refit its steps, so this is
        storage, not training.
        """
        self.model = Pipeline([("preprocess", preprocessor), ("model", model)])
        self.fitted = True

    @property
    def estimator(self):
        """The bare fitted estimator inside the artifact."""
        return self.model.named_steps["model"]

    def transformed(self, X: pd.DataFrame):
        """``X`` aligned and pushed through the fitted preprocessor."""
        return self.model.named_steps["preprocess"].transform(self.align(X))

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return np.asarray(self.model.predict(self.align(X)))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray | None:
        self.check_fitted()
        if self.task == "regression" or not hasattr(self.model, "predict_proba"):
            return None
        return np.asarray(self.model.predict_proba(self.align(X)))

    @property
    def classes_(self) -> np.ndarray | None:
        return None if self.model is None else getattr(self.model, "classes_", None)

    def save(self, run_dir: str | Path) -> dict[str, str]:
        self.check_fitted()
        joblib.dump(self.model, Path(run_dir) / MODEL_FILENAME)
        return {"model": MODEL_FILENAME}

    @classmethod
    def load(cls, run_dir: str | Path):
        run_dir = Path(run_dir)
        trainer = cls.from_spec(cls.read_spec(run_dir))
        trainer.model = joblib.load(run_dir / cls.read_files(run_dir)["model"])
        trainer.fitted = True
        return trainer


class SklearnEstimatorTrainer(PipelineArtifactTrainer):
    """A sklearn estimator fitted in one shot, inside its preprocessing."""

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "SklearnEstimatorTrainer":
        """Fit the whole pipeline on train.

        The validation split is deliberately unused: a plain sklearn
        estimator has no in-fit stopping criterion, so feeding it val data
        would only leak it. Val is scored afterwards, by the orchestrator.
        """
        model = Pipeline(
            [("preprocess", self.new_preprocessor()), ("model", self._build_model())]
        )
        model.fit(self.align(X), y, **kwargs)
        self.model = model
        self.fitted = True
        logger.info("Trained %s on %d rows", self.model_type, len(X))
        return self

    def log_model(self, tracker, input_example=None) -> None:
        """The whole pipeline, in the ``mlflow.sklearn`` flavor.

        Preprocessing included, so the logged model takes the same raw
        feature frame ``predict`` does.
        """
        self.check_fitted()
        example = None if input_example is None else self.align(input_example)
        log_flavor_model(
            tracker,
            "sklearn",
            self.model,
            input_example=example,
            predictions=None if example is None else self.model.predict(example),
        )
