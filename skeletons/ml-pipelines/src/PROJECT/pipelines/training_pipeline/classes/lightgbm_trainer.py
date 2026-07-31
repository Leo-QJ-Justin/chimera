"""``LightGBMTrainer``: the native fit path, with ``eval_set`` early stopping.

Why this is a trainer of its own rather than another entry in
``SklearnTrainer.ESTIMATORS``: LightGBM's early stopping needs the
**transformed** validation matrix at fit time, and a sklearn ``Pipeline``
cannot carry it - ``pipeline.fit(X, y, model__eval_set=...)`` would hand
the booster *untransformed* validation data, which either raises or,
worse, silently stops on a garbage curve.

So the two halves are fitted in order (preprocessor on train, booster on
the transformed matrices) and only then assembled into a ``Pipeline`` for
storage. The saved artifact is therefore identical in shape to
``SklearnTrainer``'s - one file, preprocessing and model together - and
the inference path cannot tell them apart.

Cross-validation and tuning still go through the base's sklearn path,
where there is no validation split to stop on: those runs train the full
``n_estimators`` by design, and the early-stopped fit is what the final
``train`` produces.
"""

import logging
from inspect import signature
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ..modules.preprocessing import build_preprocessor
from .base_trainer import BaseTrainer

logger = logging.getLogger(__name__)

MODEL_FILENAME = "model.joblib"


def _import_lightgbm():
    """Guarded import: the failure must name the install, not the traceback."""
    try:
        import lightgbm
    except ImportError as e:
        raise ImportError(
            "trainer.kind='lightgbm' requires the optional dependency: "
            "`uv add lightgbm` (or install the 'lightgbm' extra)"
        ) from e
    return lightgbm


class LightGBMTrainer(BaseTrainer):
    """Gradient-boosted trees with validation-driven early stopping.

    Args:
        early_stopping_rounds: Rounds without improvement on the
            validation split before the booster stops. None (or no
            validation split) trains the full ``n_estimators``.
        log_period: Rounds between eval-log lines; 0 silences them.
    """

    kind = "lightgbm"

    def __init__(
        self,
        name: str,
        params: dict | None = None,
        *,
        early_stopping_rounds: int | None = 50,
        log_period: int = 0,
        **kwargs,
    ):
        super().__init__(name, params, **kwargs)
        self.early_stopping_rounds = early_stopping_rounds
        self.log_period = log_period
        self.best_iteration: int | None = None

    def extra_spec(self) -> dict:
        return {
            "early_stopping_rounds": self.early_stopping_rounds,
            "log_period": self.log_period,
        }

    def _build_model(self):
        lightgbm = _import_lightgbm()
        cls = (
            lightgbm.LGBMRegressor
            if self.task == "regression"
            else lightgbm.LGBMClassifier
        )
        return cls(random_state=self.seed, **self.params)

    def _get_param_space(self, trial) -> dict:
        # The booster's own parameter names, unprefixed: the base tuner sets
        # them on the bare booster and folds the winners back into `params`.
        return {
            "num_leaves": trial.suggest_int("num_leaves", 15, 150),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 50, 500, step=50),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        }

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "LightGBMTrainer":
        lightgbm = _import_lightgbm()
        # Trees split on order, not magnitude, so scaling numerics would only
        # cost a transform and blur the feature values in the booster's dumps.
        preprocessor = build_preprocessor(
            self.numeric_features, self.categorical_features, scale_numeric=False
        )
        X_train_t = preprocessor.fit_transform(self.align(X))
        booster = self._build_model()

        fit_kwargs = dict(kwargs)
        if X_val is not None and y_val is not None:
            X_val_t = preprocessor.transform(self.align(X_val))
            # LightGBM 4.7 renamed `eval_set` to `eval_X`/`eval_y` and warns on
            # the old name; earlier 4.x has only the old one. Probing the
            # signature keeps the supported range wide and the log clean.
            if "eval_X" in signature(booster.fit).parameters:
                fit_kwargs.update({"eval_X": X_val_t, "eval_y": y_val})
            else:
                fit_kwargs["eval_set"] = [(X_val_t, y_val)]
            callbacks = []
            if self.early_stopping_rounds:
                callbacks.append(
                    lightgbm.early_stopping(self.early_stopping_rounds, verbose=False)
                )
            if self.log_period:
                callbacks.append(lightgbm.log_evaluation(period=self.log_period))
            fit_kwargs["callbacks"] = callbacks
        else:
            logger.warning(
                "No validation split given; LightGBM will train the full "
                "n_estimators with no early stopping"
            )

        booster.fit(X_train_t, y, **fit_kwargs)
        self.best_iteration = getattr(booster, "best_iteration_", None)
        # Assembled after both halves are fitted: constructing a Pipeline
        # does not refit its steps, so this is storage, not training.
        self.model = Pipeline([("preprocess", preprocessor), ("model", booster)])
        self.fitted = True
        logger.info(
            "Trained %s on %d rows (best_iteration=%s of %s)",
            self.model_type,
            len(X),
            self.best_iteration,
            self.params.get("n_estimators"),
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return np.asarray(self.model.predict(self.align(X)))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray | None:
        self.check_fitted()
        if self.task == "regression":
            return None
        return np.asarray(self.model.predict_proba(self.align(X)))

    @property
    def classes_(self) -> np.ndarray | None:
        return None if self.model is None else getattr(self.model, "classes_", None)

    def training_summary(self) -> dict:
        return {
            "best_iteration": self.best_iteration,
            "early_stopping_rounds": self.early_stopping_rounds,
        }

    def get_params(self) -> dict:
        params = super().get_params()
        params["early_stopping_rounds"] = self.early_stopping_rounds
        if self.best_iteration is not None:
            params["best_iteration"] = self.best_iteration
        return params

    def save(self, run_dir: str | Path) -> dict[str, str]:
        self.check_fitted()
        joblib.dump(self.model, Path(run_dir) / MODEL_FILENAME)
        return {"model": MODEL_FILENAME}

    @classmethod
    def load(cls, run_dir: str | Path) -> "LightGBMTrainer":
        run_dir = Path(run_dir)
        trainer = cls.from_spec(cls.read_spec(run_dir))
        trainer.model = joblib.load(run_dir / cls.read_files(run_dir)["model"])
        trainer.fitted = True
        return trainer
