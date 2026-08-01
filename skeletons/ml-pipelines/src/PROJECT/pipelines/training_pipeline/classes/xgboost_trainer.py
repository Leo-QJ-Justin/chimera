"""``XGBoostTrainer``: the other boosting family, with its own fit path.

Same reason LightGBM has one: early stopping needs the **transformed**
validation matrix at fit time, which a sklearn ``Pipeline.fit`` signature
cannot carry. The difference from LightGBM is in the wiring -
``early_stopping_rounds`` is a *constructor* argument in xgboost >= 1.6,
not a fit argument or a callback, and setting it without an ``eval_set``
raises. So it is attached in :meth:`train`, only once there is something
to stop on, which also leaves ``_build_model`` usable for the CV and
tuning paths.

Cross-validation and tuning both give a fit its referee rather than doing
without one: a CV fold carves a stopping subset out of its own training
rows (R1.11), and the search carves one holdout up front that every trial
early-stops against and is then scored on. So a tuned ``n_estimators`` is
the ceiling a trial stopped short of, not a round count anyone trained to
the end.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ....schemas import FloatSpace, IntSpace, ParamSpace
from ...evaluation_pipeline.modules.metrics import compute_metrics, log_metrics, prefixed
from ..modules.history import booster_history
from ..modules.model_logging import log_flavor_model
from .base_trainer import (
    TUNE_HOLDOUT_FRACTION,
    BaseTrainer,
    FitFrames,
    _import_optuna,
    resolve_tune_metric,
)

logger = logging.getLogger(__name__)

MODEL_FILENAME = "model.joblib"


def _import_xgboost():
    """Guarded import: the failure must name the install, not the traceback."""
    try:
        import xgboost
    except ImportError as e:
        raise ImportError(
            "trainer.kind='xgboost' requires the optional dependency: "
            "`uv add xgboost` (or install the 'xgboost' extra)"
        ) from e
    return xgboost


class XGBoostTrainer(BaseTrainer):
    """Gradient-boosted trees with validation-driven early stopping.

    Args:
        early_stopping_rounds: Rounds without improvement on the
            validation split before the booster stops. None (or no
            validation split) trains the full ``n_estimators``.
        log_period: Rounds between eval-log lines; 0 silences them.
    """

    kind = "xgboost"
    scale_numeric = False
    # Early stopping reads the validation curve during the fit, so val must
    # stay outside the training data: standing-val protocol (R1.10).
    uses_val_in_fit = True

    # Defaults for the search; `trainer.tune.space` narrows any of them and
    # `false` drops one, leaving whatever `params` configured.
    TUNABLE: ClassVar[dict[str, ParamSpace]] = {
        # xgboost's `eta`, under the sklearn API's name for it.
        "learning_rate": FloatSpace(low=0.01, high=0.3, log=True),
        "max_depth": IntSpace(low=2, high=10),
        "subsample": FloatSpace(low=0.6, high=1.0),
        "colsample_bytree": FloatSpace(low=0.6, high=1.0),
        "min_child_weight": IntSpace(low=1, high=20),
        "n_estimators": IntSpace(low=50, high=500, step=50),
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
        xgboost = _import_xgboost()
        booster = (
            xgboost.XGBRegressor if self.task == "regression" else xgboost.XGBClassifier
        )
        return booster(random_state=self.seed, **self.params)

    def _get_param_space(self, trial, space: dict) -> dict:
        return {name: entry.suggest(trial, name) for name, entry in space.items()}

    def fit_frames(self, X: dict, y: dict) -> FitFrames:
        """The standing-val protocol: fit on train, val stays the referee.

        Val is handed back as the referee frames rather than pooled into the
        fit, because that is exactly what this family's early stopping reads
        during the fit - rows inside the training data cannot referee it
        (R1.10). Test is untouched either way.
        """
        return FitFrames(X["train"], y["train"], X["val"], y["val"], ["train"])

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "XGBoostTrainer":
        preprocessor = self.new_preprocessor()
        X_train_t = preprocessor.fit_transform(self.align(X))
        booster = self._build_model()

        fit_kwargs = dict(kwargs)
        if X_val is not None and y_val is not None:
            if self.early_stopping_rounds:
                booster.set_params(early_stopping_rounds=self.early_stopping_rounds)
            fit_kwargs["eval_set"] = [(preprocessor.transform(self.align(X_val)), y_val)]
            fit_kwargs.setdefault("verbose", self.log_period or False)
        else:
            logger.warning(
                "No validation split given; XGBoost will train the full "
                "n_estimators with no early stopping"
            )

        booster.fit(X_train_t, y, **fit_kwargs)
        # None until a stopping round actually fires, so it doubles as the
        # record of whether early stopping engaged.
        self.best_iteration = getattr(booster, "best_iteration", None)
        # Capture only: the orchestrator replays history into the tracker, so
        # the trainer stays free of tracking and plotting code. Guarded on the
        # eval set because there is nothing recorded without one.
        self.history = (
            booster_history(booster.evals_result()) if fit_kwargs.get("eval_set") else []
        )
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

    def evaluate_run(
        self,
        X: dict,
        y: dict,
        X_fit: pd.DataFrame,
        y_fit,
        *,
        metric: str,
        cv: int,
        basis: str,
        split: str,
    ) -> dict[str, float]:
        """Every named split scored, plus the CV estimate under ``basis: cv``.

        Val stayed outside the fit, so it is a genuinely held-out number and
        is published as one; train is scored too, as the overfitting
        reference. ``X_fit``/``y_fit`` are accepted and unread - this
        protocol scores the named splits, and the signature is the same for
        every family.

        Under ``selection.basis: cv`` the fit above is untouched - this
        family's early stopping still needs its standing referee - but the
        number ``best.json`` records becomes a procedure CV over the
        train+val pool, where each fold carves its own referee (R1.11). That
        is what a pooled family's ``cv_`` number already is, so the two rank
        against each other. The std travels with the mean because a
        selection criterion is a random variable: two runs 0.002 apart on a
        fold spread of 0.05 have not been distinguished (Cawley & Talbot
        2010).
        """
        metrics: dict[str, float] = {}
        for name in ("train", "val", "test"):
            split_metrics = self.evaluate(X[name], y[name])
            log_metrics(split_metrics, name)
            metrics.update(prefixed(split_metrics, name))
        if basis != "cv":
            return metrics

        logger.info(
            "selection.basis=cv: %s keeps its standing-val fit, and best.json "
            "reads a procedure-CV estimate on train+val instead of %s_%s",
            self.model_type,
            split,
            metric,
        )
        # Pooled in split order, so a temporal run's pool stays chronological,
        # which is what lets a fold carve its stopping subset off the end of
        # its own training window rather than out of the middle of it.
        X_pool = pd.concat([X["train"], X["val"]])
        y_pool = pd.concat([y["train"], y["val"]])
        stats = self.cross_validate(X_pool, y_pool, cv=cv, metrics=[metric])[metric]
        logger.info(
            "CV estimate on train+val: %s = %.4f +/- %.4f over %d folds",
            metric,
            stats["mean"],
            stats["std"],
            cv,
        )
        metrics[f"cv_{metric}"] = stats["mean"]
        metrics[f"cv_{metric}_std"] = stats["std"]
        return metrics

    def selection_key(self, *, metric: str, basis: str, split: str) -> tuple[str, str]:
        """The configured split's score, unless the run asked for the CV basis.

        Val stayed outside the fit, so ``selection.split`` names a real
        out-of-sample number and is honoured. ``selection.basis: cv`` trades
        it for the procedure-CV estimate every family can publish, which is
        what makes runs of different families rankable in one output
        directory (R1.11).
        """
        if basis == "cv":
            return "cv", f"cv_{metric}"
        return split, f"{split}_{metric}"

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
    def load(cls, run_dir: str | Path) -> "XGBoostTrainer":
        run_dir = Path(run_dir)
        trainer = cls.from_spec(cls.read_spec(run_dir))
        trainer.model = joblib.load(run_dir / cls.read_files(run_dir)["model"])
        trainer.fitted = True
        return trainer

    def log_model(self, tracker, input_example=None) -> None:
        """The bare booster, in the ``mlflow.xgboost`` flavor.

        The flavor stores an XGBoost model, not a sklearn pipeline, so the
        example is transformed first and the recorded signature describes
        what the artifact actually accepts.
        """
        self.check_fitted()
        example = None if input_example is None else self.transformed(input_example)
        log_flavor_model(
            tracker,
            "xgboost",
            self.estimator,
            input_example=example,
            predictions=None if example is None else self.estimator.predict(example),
        )
