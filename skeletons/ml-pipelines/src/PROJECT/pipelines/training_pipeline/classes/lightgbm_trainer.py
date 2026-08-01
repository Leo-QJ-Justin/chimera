"""``LightGBMTrainer``: the native fit path, with ``eval_set`` early stopping.

Why its early stopping needs a fit path of its own: it wants the
**transformed** validation matrix at fit time, and a sklearn ``Pipeline``
cannot carry one - ``pipeline.fit(X, y, model__eval_set=...)`` hands the
booster *untransformed* validation data, which either raises or, worse,
silently stops on a garbage curve.

So the two halves are fitted in order (preprocessor on train, booster on
the transformed matrices) and only then assembled into one
``Pipeline`` artifact, which makes a LightGBM run indistinguishable from
any other at serving time.

Cross-validation and tuning both give a fit its referee rather than doing
without one: a CV fold carves a stopping subset out of its own training
rows (R1.11), and the search carves one holdout up front that every trial
early-stops against and is then scored on. So a tuned ``n_estimators`` is
the ceiling a trial stopped short of, not a round count anyone trained to
the end.
"""

import logging
from collections.abc import Callable
from inspect import signature
from pathlib import Path
from typing import Any, ClassVar

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ....schemas import FloatSpace, IntSpace, ParamSpace
from ...evaluation_pipeline.modules.metrics import compute_metrics
from ..modules.history import booster_history
from ..modules.model_logging import log_flavor_model
from .base_trainer import (
    TUNE_HOLDOUT_FRACTION,
    BaseTrainer,
    _import_optuna,
    resolve_tune_metric,
)

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
    scale_numeric = False
    # Early stopping reads the validation curve during the fit, so val must
    # stay outside the training data: standing-val protocol (R1.10).
    uses_val_in_fit = True

    # Defaults for the search; `trainer.tune.space` narrows any of them and
    # `false` drops one, leaving whatever `params` configured.
    TUNABLE: ClassVar[dict[str, ParamSpace]] = {
        "num_leaves": IntSpace(low=15, high=150),
        "learning_rate": FloatSpace(low=0.01, high=0.3, log=True),
        "n_estimators": IntSpace(low=50, high=500, step=50),
        "min_child_samples": IntSpace(low=5, high=100),
        "colsample_bytree": FloatSpace(low=0.6, high=1.0),
        "reg_lambda": FloatSpace(low=1e-8, high=10.0, log=True),
    }

    def __init__(
        self,
        params: dict | None = None,
        *,
        early_stopping_rounds: int | None = 50,
        log_period: int = 0,
        **kwargs,
    ):
        super().__init__(params, **kwargs)
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
        booster = (
            lightgbm.LGBMRegressor
            if self.task == "regression"
            else lightgbm.LGBMClassifier
        )
        return booster(random_state=self.seed, **self.params)

    def _get_param_space(self, trial, space: dict) -> dict:
        return {name: entry.suggest(trial, name) for name, entry in space.items()}

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "LightGBMTrainer":
        lightgbm = _import_lightgbm()
        preprocessor = self.new_preprocessor()
        X_train_t = preprocessor.fit_transform(self.align(X))
        booster = self._build_model()

        fit_kwargs = dict(kwargs)
        # Filled in place by the record_evaluation callback below; stays empty
        # when there is no eval set to record.
        evals_result: dict = {}
        if X_val is not None and y_val is not None:
            X_val_t = preprocessor.transform(self.align(X_val))
            # LightGBM 4.7 renamed `eval_set` to `eval_X`/`eval_y` and warns on
            # the old name; earlier 4.x has only the old one. Probing the
            # signature keeps the supported range wide and the log clean.
            if "eval_X" in signature(booster.fit).parameters:
                fit_kwargs.update({"eval_X": X_val_t, "eval_y": y_val})
            else:
                fit_kwargs["eval_set"] = [(X_val_t, y_val)]
            # Capture only: the orchestrator replays history into the tracker,
            # so the trainer stays free of tracking and plotting code.
            callbacks = [lightgbm.record_evaluation(evals_result)]
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
        self.history = booster_history(evals_result)
        self.assemble(preprocessor, booster)
        logger.info(
            "Trained %s on %d rows (best_iteration=%s of %s)",
            self.model_type,
            len(X),
            self.best_iteration,
            self.params.get("n_estimators"),
        )
        return self

    def assemble(self, preprocessor, booster) -> None:
        """Store the two already-fitted halves as the one artifact.

        Constructing a ``Pipeline`` does not refit its steps, so this is
        storage, not training - which is the whole reason the halves could
        be fitted separately in the first place.
        """
        self.model = Pipeline([("preprocess", preprocessor), ("model", booster)])
        self.fitted = True

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

    def evaluate(
        self, X: pd.DataFrame, y, metrics: list[str | Callable] | None = None
    ) -> dict[str, float]:
        """Score a frame with the project's metric definitions."""
        self.check_fitted()
        return compute_metrics(y, self.predict(X), task=self.task, metrics=metrics)

    def hyperparameter_tune(
        self,
        X: pd.DataFrame,
        y,
        n_trials: int = 100,
        cv: int | Any = 5,
        metric: str | None = None,
        direction: str | None = None,
        space: dict | None = None,
        **optuna_kwargs,
    ) -> dict:
        """Optuna over one carved holdout, which every trial early-stops on.

        One holdout is carved off the search frames up front (the
        chronological tail under ``cv_mode: temporal``), and each trial
        trains a candidate against it and is then scored on it through
        :meth:`evaluate`. That is this family's real procedure: a booster
        without a referee trains its full ``n_estimators``, so a k-fold
        search would rank candidates by a fit shaped unlike the one the run
        ships. ``cv`` is therefore **not read here** - it still sets the fold
        count of the selection CV under ``selection.basis: cv``.

        Known bias: trials are scored on the same rows they early-stopped
        against, so the winning score is optimistic. The honest number
        remains the training pipeline's untouched test split.

        Args:
            n_trials: Optuna trials; each costs one early-stopped fit.
            cv: Ignored by this search (see above).
            metric: A project metric alias; None -> the task default.
            direction: None -> inferred from the metric.
            space: ``trainer.tune.space`` overrides of :attr:`TUNABLE`.

        Returns:
            The best parameters found, already folded into ``params``.

        Raises:
            ImportError: If optuna is not installed.
        """
        optuna = _import_optuna()
        metric, direction = resolve_tune_metric(self.task, metric, direction)
        merged = self._merged_space(space)
        X_fit, y_fit, X_stop, y_stop = self._carve_stopping_subset(
            self.align(X), np.asarray(y), TUNE_HOLDOUT_FRACTION
        )
        logger.info(
            "Tuning %s over %d trials: %s (%s), %d rows fitted against a "
            "%d-row holdout per trial, searching %s",
            self.model_type,
            n_trials,
            metric,
            direction,
            len(X_fit),
            len(X_stop),
            sorted(merged),
        )

        def objective(trial) -> float:
            resolved = self._get_param_space(trial, merged)
            # Recorded on the trial rather than left to study.best_params,
            # which holds only what Optuna itself suggested - the two agree
            # for this family and would silently stop agreeing the day the
            # space derives anything.
            trial.set_user_attr("resolved_params", resolved)
            candidate = self.fresh()
            candidate.params.update(resolved)
            candidate.train(X_fit, y_fit, X_stop, y_stop)
            return candidate.evaluate(X_stop, y_stop, metrics=[metric])[metric]

        study = optuna.create_study(direction=direction, **optuna_kwargs)
        # show_progress_bar is off: the bar writes to stderr and interleaves
        # with the run's log file, which is the thing anyone reads afterwards.
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        self.best_params = dict(study.best_trial.user_attrs["resolved_params"])
        self.params.update(self.best_params)
        logger.info(
            "Tuned %s over %d trials: best %s=%.6f with %s",
            self.model_type,
            n_trials,
            metric,
            study.best_value,
            self.best_params,
        )
        return self.best_params

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

    @property
    def estimator(self):
        """The bare fitted booster inside the artifact."""
        return self.model.named_steps["model"]

    @property
    def preprocessor(self):
        """The fitted preprocessor half of the artifact.

        Named as every other family names it, so post-fit diagnostics can
        ask any trainer for its transformer without branching on which one
        it got.
        """
        return self.model.named_steps["preprocess"]

    def transformed(self, X: pd.DataFrame):
        """``X`` aligned and pushed through the fitted preprocessor."""
        return self.preprocessor.transform(self.align(X))

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

    def log_model(self, tracker, input_example=None) -> None:
        """The bare booster, in the ``mlflow.lightgbm`` flavor.

        The flavor stores a LightGBM model, not a sklearn pipeline, so the
        logged model takes the *transformed* design matrix - which is what
        the example is transformed into here, so the recorded signature
        describes what the artifact actually accepts.
        """
        self.check_fitted()
        example = None if input_example is None else self.transformed(input_example)
        log_flavor_model(
            tracker,
            "lightgbm",
            self.estimator,
            input_example=example,
            predictions=None if example is None else self.estimator.predict(example),
        )
