"""``LogisticRegressionTrainer``: the linear classification baseline.

Its own class rather than a row in a generic estimator table: a family is
defined by its search space as much as by its constructor, and logistic
regression's is coupled (penalty, solver and ``l1_ratio`` are only legal in
certain combinations). That coupling has nowhere to live in a shared
lookup table.

Self-contained on purpose, down to the parts a sibling file repeats almost
verbatim (the one-shot fit, the joblib pair, the sklearn flavor): the file
is meant to answer "what does this family do?" from top to bottom, and
every hop up an inheritance chain is a place that question stops being
answerable here.

The artifact is one ``Pipeline(preprocess, model)`` (D6): ``joblib.dump``
captures preprocessing and model *together*, so they cannot drift apart at
serving time, and per-fold refitting is automatic rather than remembered.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ....schemas import ChoiceSpace, FloatSpace, ParamSpace
from ...evaluation_pipeline.modules.metrics import compute_metrics
from ..modules.model_logging import log_flavor_model
from .base_trainer import BaseTrainer, _import_optuna, resolve_tune_metric

logger = logging.getLogger(__name__)

MODEL_FILENAME = "model.joblib"


class LogisticRegressionTrainer(BaseTrainer):
    """Regularised linear classifier, fitted inside its preprocessing."""

    kind = "logreg"
    # A one-shot sklearn fit has no in-fit stopping criterion, so it never
    # looks at val. Its runs therefore tune and select on train+val pooled,
    # with a k-fold CV estimate as the selection number (R1.10).
    uses_val_in_fit = False

    # Defaults for the search; `trainer.tune.space` narrows any of them and
    # `false` drops one. `l1_ratio` is only read under an elasticnet penalty,
    # which only saga supports - see _get_param_space for the coupling.
    TUNABLE: ClassVar[dict[str, ParamSpace]] = {
        "C": FloatSpace(low=1e-3, high=1e2, log=True),
        "solver": ChoiceSpace(choices=["lbfgs", "saga"]),
        "class_weight": ChoiceSpace(choices=[None, "balanced"]),
        "l1_ratio": FloatSpace(low=0.0, high=1.0),
    }

    def _build_model(self):
        if self.task != "classification":
            raise ValueError(
                f"trainer.kind='logreg' is a classifier, not task={self.task!r}; "
                "use trainer=random_forest (or another regressor) instead"
            )
        return LogisticRegression(random_state=self.seed, **self.params)

    def _get_param_space(self, trial, space: dict) -> dict:
        # Suggest the solver first and derive the penalty from it: elasticnet
        # exists only under saga, and l1_ratio is read only under elasticnet,
        # so sampling them independently would spend trials on illegal
        # combinations. The derived keys survive because hyperparameter_tune
        # records the resolved dict, not just what Optuna suggested.
        resolved = {
            name: entry.suggest(trial, name)
            for name, entry in space.items()
            if name != "l1_ratio"
        }
        # The configured solver stands in when the search is not sampling one.
        solver = resolved.get("solver", self.params.get("solver"))
        if solver == "saga" and "l1_ratio" in space:
            resolved["penalty"] = "elasticnet"
            resolved["l1_ratio"] = space["l1_ratio"].suggest(trial, "l1_ratio")
        return resolved

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "LogisticRegressionTrainer":
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

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return np.asarray(self.model.predict(self.align(X)))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray | None:
        self.check_fitted()
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
        """Optuna, scoring every trial by this family's own procedure CV.

        A trial is a candidate trainer of this same spec, cross-validated by
        :meth:`BaseTrainer.cross_validate` - which fits it fold by fold
        exactly as the run will fit the winner, and scores each fold through
        :meth:`evaluate`. So the number a trial is ranked on is the number
        the run publishes, in the same units, and the selection CV that
        decides ``best.json`` measures the same thing the search did.

        Args:
            n_trials: Optuna trials; each costs ``cv`` fits.
            cv: Fold count (the splitter follows ``cv_mode``) or a splitter.
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
        logger.info(
            "Tuning %s over %d trials: %s (%s), %d folds per trial, searching %s",
            self.model_type,
            n_trials,
            metric,
            direction,
            cv if isinstance(cv, int) else cv.get_n_splits(),
            sorted(merged),
        )

        def objective(trial) -> float:
            resolved = self._get_param_space(trial, merged)
            # study.best_params holds only what was *suggested*; this space
            # derives a value from a suggestion (the penalty that goes with
            # saga), which would be lost. Record the resolved dict here and
            # read it back off the winning trial.
            trial.set_user_attr("resolved_params", resolved)
            candidate = self.fresh()
            candidate.params.update(resolved)
            scores = candidate.cross_validate(X, y, cv=cv, metrics=[metric])
            return scores[metric]["mean"]

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

    @property
    def estimator(self):
        """The bare fitted estimator inside the artifact."""
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
    def load(cls, run_dir: str | Path) -> "LogisticRegressionTrainer":
        run_dir = Path(run_dir)
        trainer = cls.from_spec(cls.read_spec(run_dir))
        trainer.model = joblib.load(run_dir / cls.read_files(run_dir)["model"])
        trainer.fitted = True
        return trainer

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
