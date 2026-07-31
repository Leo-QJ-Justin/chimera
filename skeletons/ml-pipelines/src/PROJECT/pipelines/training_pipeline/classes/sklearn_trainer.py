"""``SklearnTrainer``: preprocessing + estimator as one sklearn Pipeline.

D6 in code. The fitted ``ColumnTransformer`` and the estimator live in a
single ``Pipeline``, which buys three things a hand-rolled pair does not:
per-fold refitting is automatic under ``cross_validate``/Optuna tuning
(leakage-as-architecture, solved structurally), ``joblib.dump`` captures
preprocessing and model *together* so they can never drift apart at
serving time, and ``sklearn.clone`` round-trips the whole thing from its
params.

Adding a family is an entry in ``ESTIMATORS`` (builder + search space)
plus a ``configs/trainer/<name>.yaml``. Every registered name has a group
file, so ``trainer=<name>`` is always the way to switch.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ..modules.preprocessing import build_preprocessor
from .base_trainer import BaseTrainer

logger = logging.getLogger(__name__)

MODEL_FILENAME = "model.joblib"


def _logreg(params: dict, seed: int, task: str):
    return LogisticRegression(random_state=seed, **params)


def _logreg_space(trial) -> dict:
    return {
        "C": trial.suggest_float("C", 1e-3, 1e2, log=True),
        "class_weight": trial.suggest_categorical("class_weight", [None, "balanced"]),
    }


def _random_forest(params: dict, seed: int, task: str):
    cls = RandomForestRegressor if task == "regression" else RandomForestClassifier
    return cls(random_state=seed, n_jobs=-1, **params)


def _random_forest_space(trial) -> dict:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=50),
        "max_depth": trial.suggest_int("max_depth", 3, 20),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 20),
    }


# name -> (builder, search space, supported tasks). The task tuple is what
# turns "wrong model for this problem" into a config error with a sentence,
# instead of a sklearn traceback about continuous targets 200 lines into a fit.
#
# Search-space keys are the estimator's own parameter names, unprefixed: the
# base tuner sets them on the bare estimator before wrapping it in the
# preprocessing pipeline, and folds the winners straight back into `params`.
ESTIMATORS: dict[str, tuple] = {
    "logreg": (_logreg, _logreg_space, ("classification",)),
    "random_forest": (
        _random_forest,
        _random_forest_space,
        ("classification", "regression"),
    ),
}


class SklearnTrainer(BaseTrainer):
    """Any sklearn-API estimator, wrapped with its fitted preprocessing."""

    kind = "sklearn"

    def _entry(self) -> tuple:
        if self.name not in ESTIMATORS:
            raise KeyError(
                f"Unknown sklearn estimator {self.name!r}; registered: "
                f"{sorted(ESTIMATORS)}. Add an entry to ESTIMATORS and a "
                "configs/trainer/<name>.yaml."
            )
        builder, space, tasks = ESTIMATORS[self.name]
        if self.task not in tasks:
            raise ValueError(
                f"Estimator {self.name!r} supports {list(tasks)}, not task={self.task!r}"
            )
        return builder, space, tasks

    def _build_model(self):
        builder, _, _ = self._entry()
        return builder(dict(self.params), self.seed, self.task)

    def _get_param_space(self, trial) -> dict:
        _, space, _ = self._entry()
        return space(trial)

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "SklearnTrainer":
        """Fit the whole pipeline on train.

        The validation split is deliberately unused: a plain sklearn
        estimator has no in-fit stopping criterion, so feeding it val data
        would only leak it. Val is scored afterwards, by the orchestrator.
        """
        self.model = Pipeline(
            [
                (
                    "preprocess",
                    build_preprocessor(self.numeric_features, self.categorical_features),
                ),
                ("model", self._build_model()),
            ]
        )
        self.model.fit(self.align(X), y, **kwargs)
        self.fitted = True
        logger.info("Trained %s on %d rows", self.model_type, len(X))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return np.asarray(self.model.predict(self.align(X)))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray | None:
        self.check_fitted()
        if not hasattr(self.model, "predict_proba"):
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
    def load(cls, run_dir: str | Path) -> "SklearnTrainer":
        run_dir = Path(run_dir)
        trainer = cls.from_spec(cls.read_spec(run_dir))
        trainer.model = joblib.load(run_dir / cls.read_files(run_dir)["model"])
        trainer.fitted = True
        return trainer
