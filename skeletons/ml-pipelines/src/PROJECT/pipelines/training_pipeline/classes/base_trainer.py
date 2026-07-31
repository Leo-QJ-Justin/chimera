"""``BaseTrainer``: the one contract every model family is reached through.

The training pipeline builds a trainer from the ``trainer/`` config group
and then only ever calls the methods below. That is what keeps the
orchestrator free of ``if trainer.kind == ...`` branches, and what lets the
inference pipeline reload a torch run and a LightGBM run with identical
code.

Subclasses implement ``_build_model``, ``_get_param_space``,
``train``/``predict`` and ``save``/``load``. In exchange the base gives
them ``evaluate``, ``cross_validate`` and ``hyperparameter_tune`` - the
three places per-family reimplementations drift apart.

Four decisions the rest of the file assumes:

- **Validation data is in ``train``'s signature**, not out-of-band state,
  because three shipped trainers need it during the fit (LightGBM and
  XGBoost early stopping, torch's per-epoch monitor). A trainer with no
  use for it ignores it - and says so through ``uses_val_in_fit``, which
  is what picks the run's tuning and selection protocol (R1.10) and, inside
  ``cross_validate``, whether each fold carves its own stopping subset
  (R1.11).
- **``predict_proba`` may return None.** The inference pipeline degrades to
  hard predictions rather than making every family fake probabilities.
- **One artifact, named in metadata.** ``save`` returns the
  ``{kind: filename}`` map that goes verbatim into ``metadata.json``, so
  nothing downstream globs a directory. ``load`` is metadata-first and
  never consults config files, which may have moved on since the run.
- **``get_params`` and ``spec`` stay separate.** The tracker wants
  ``model_lr=0.001``; the reload path wants a nested structure it can hand
  back to ``__init__``.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from sklearn.model_selection import cross_validate as sk_cross_validate
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ....core.run_artifacts import load_metadata
from ...evaluation_pipeline.modules.metrics import compute_metrics
from ..modules.preprocessing import build_preprocessor
from ..modules.splitting import make_cv_splitter

logger = logging.getLogger(__name__)

# sklearn *scoring* strings (not metric-function names), for the tuner -
# which scores through sklearn's own cross_validate.
TUNE_METRIC = {"classification": "f1_macro", "regression": "neg_root_mean_squared_error"}
# Share of each CV fold's training rows carved out as the early-stopping
# referee, for families whose fit needs one (R1.11). Matches the standing
# val split's share of the run, so a fold's fit is shaped like the real one.
CV_STOP_FRACTION = 0.15


def _import_optuna():
    """Guarded import: the failure must name the install, not the traceback."""
    try:
        import optuna
    except ImportError as e:
        raise ImportError(
            "hyperparameter_tune requires the optional dependency optuna: "
            "`uv add optuna` (or install the 'tune' extra)"
        ) from e
    return optuna


class BaseTrainer(ABC):
    """Train / predict / evaluate / cross-validate / tune / save / load.

    Args:
        params: The family's own hyperparameters, passed through to its
            constructor untouched so a typo raises there, loudly.
        task: ``"classification"`` or ``"regression"``.
        seed: The single run seed, threaded into ``_build_model`` and into
            every RNG the family has.
        numeric_features: Numeric feature columns, in contract order.
        categorical_features: Categorical feature columns, in contract
            order. Concatenated after the numerics to form
            ``feature_columns``, which metadata pins for inference.
        cv_mode: The run's ``split.mode``; picks the CV splitter (D9).

    Attributes:
        kind: Registry key, config ``trainer.kind``, and ``model_type`` in
            metadata - one name for one family.
        scale_numeric: Whether this family's preprocessing standardises
            numerics. Trees set it False; splits are scale-invariant.
        uses_val_in_fit: Whether ``train`` consumes the validation split.
            The training pipeline reads it to pick the protocol (R1.10):
            True keeps val a standing referee outside the fit, False pools
            train+val and selects on a k-fold CV estimate.
        best_params: Set by :meth:`hyperparameter_tune`; folded into
            ``params`` so the next ``train`` uses them.
        history: Per-iteration records for trainers that have iterations.
    """

    kind: ClassVar[str] = ""
    scale_numeric: ClassVar[bool] = True
    # Annotated, never defaulted: whether a family's fit consumes val decides
    # which tuning and selection protocol its runs follow, and a default here
    # would answer that question for a new family before anyone asked it.
    # Every concrete trainer states its own (tests/test_trainers.py enforces
    # that it is declared in the family's own class body).
    uses_val_in_fit: ClassVar[bool]

    def __init__(
        self,
        params: dict | None = None,
        *,
        task: str = "classification",
        seed: int = 42,
        numeric_features: list[str] | None = None,
        categorical_features: list[str] | None = None,
        cv_mode: str = "stratified",
    ):
        self.params = dict(params or {})
        self.task = task
        self.seed = seed
        self.numeric_features = list(numeric_features or [])
        self.categorical_features = list(categorical_features or [])
        self.cv_mode = cv_mode
        self.best_params: dict | None = None
        self.fitted = False
        # The fitted artifact. Deliberately NOT built in __init__: a torch
        # module needs the design-matrix width, which only exists once data
        # has been transformed.
        self.model: Any = None
        # The orchestrator replays these into the tracker after training,
        # which is why train() needs no tracker argument and the trainers
        # stay free of tracking code.
        self.history: list[dict] = []

    # ------------------------------------------------------- abstract hooks

    @abstractmethod
    def _build_model(self) -> Any:
        """A **fresh**, unfitted, seeded estimator from ``params``.

        Called once per ``train``, once per CV fold and once per tuning
        trial. It must never return a shared object: that is what keeps
        cross-validation honest.
        """

    @abstractmethod
    def _get_param_space(self, trial) -> dict:
        """This family's Optuna space: parameter name -> suggested value."""

    @abstractmethod
    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "BaseTrainer":
        """Fit preprocessing and model. Returns ``self`` for chaining."""

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Hard predictions: class labels, or values for regression."""

    @abstractmethod
    def save(self, run_dir: str | Path) -> dict[str, str]:
        """Write this trainer's artifacts into ``run_dir``.

        Returns:
            ``{kind: filename}`` for ``metadata.json``'s ``files`` map.
            Filenames only, never paths - the run dir resolves them, and it
            moves.
        """

    @classmethod
    @abstractmethod
    def load(cls, run_dir: str | Path) -> "BaseTrainer":
        """Rebuild a fitted trainer from a run directory (metadata-first)."""

    # ------------------------------------------------------------ optional

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray | None:
        """Class probabilities, or None when the family has none."""
        return None

    @property
    def classes_(self) -> np.ndarray | None:
        """Class labels in the order ``predict_proba`` returns them."""
        return None

    def training_summary(self) -> dict:
        """Per-run detail for ``metadata.json``'s ``training_info``."""
        return {}

    def log_model(self, tracker, input_example=None) -> None:
        """Log the fitted model to ``tracker`` in this family's MLflow flavor.

        Called by the training pipeline after ``train``, when tracking is
        live. Implementations delegate to
        ``..modules.model_logging.log_flavor_model``; the default is a
        no-op, so a family without a flavor is not a failure.
        """
        logger.debug("%s logs no MLflow model", type(self).__name__)

    # -------------------------------------------------- concrete services

    def evaluate(
        self, X: pd.DataFrame, y, metrics: list[str | Callable] | None = None
    ) -> dict[str, float]:
        """Score a frame with the project's metric definitions.

        Args:
            X: Features, in any column order (realigned internally).
            y: Ground truth.
            metrics: Metric names or callables; None -> the task defaults.
        """
        self.check_fitted()
        return compute_metrics(y, self.predict(X), task=self.task, metrics=metrics)

    def cross_validate(
        self,
        X: pd.DataFrame,
        y,
        cv: int | Any = 5,
        metrics: list[str | Callable] | None = None,
        stop_fraction: float = CV_STOP_FRACTION,
    ) -> dict[str, dict[str, float | list[float]]]:
        """Cross-validate the **whole training procedure**, fold by fold.

        Every fold builds a fresh trainer of this spec and runs the
        family's real :meth:`train` on the fold's training rows - including,
        for a family whose fit needs a stopping referee, a carve-out taken
        from *inside* those rows (R1.11). The run's standing validation
        split plays no part here, which is what makes the estimate
        comparable across families: every candidate is measured by the same
        procedure on the same folds, and none of them has seen test.

        The cost is honest and unhidden: ``cv`` full fits of this family,
        early stopping and all.

        Args:
            X: Features.
            y: Target.
            cv: Fold count (the splitter then follows ``cv_mode``, per D9)
                or an explicit sklearn splitter.
            metrics: Project metric names or callables, exactly as
                :meth:`evaluate` takes them - so a fold score is the same
                measurement the report and ``best.json`` print. None -> the
                task defaults.
            stop_fraction: Share of a fold's training rows carved out as
                the early-stopping referee. Ignored by families whose fit
                does not use one.

        Returns:
            ``{metric: {"mean": ..., "std": ..., "values": [per fold]}}``.
            The spread travels with the mean because a fold mean is a
            random variable, not a measurement (Cawley & Talbot 2010).
        """
        X_aligned = self.align(X)
        y_values = np.asarray(y)
        splitter = self._splitter(cv)
        folds = splitter.get_n_splits(X_aligned, y_values)
        logger.info(
            "Cross-validating %s: %d full fits%s",
            self.model_type,
            folds,
            ", each carving its own stopping subset" if self.uses_val_in_fit else "",
        )

        scores: dict[str, list[float]] = {}
        for fold, (fit_rows, held_rows) in enumerate(splitter.split(X_aligned, y_values)):
            candidate = self.fresh()
            X_fold, y_fold = X_aligned.iloc[fit_rows], y_values[fit_rows]
            if self.uses_val_in_fit:
                carved = self._carve_stopping_subset(X_fold, y_fold, stop_fraction)
                candidate.train(*carved)
            else:
                candidate.train(X_fold, y_fold)
            fold_scores = candidate.evaluate(
                X_aligned.iloc[held_rows], y_values[held_rows], metrics=metrics
            )
            logger.debug("Fold %d/%d: %s", fold + 1, folds, fold_scores)
            for name, value in fold_scores.items():
                scores.setdefault(name, []).append(value)

        logger.info("Cross-validated %s over %d folds", self.model_type, folds)
        return {
            name: {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "values": [float(v) for v in values],
            }
            for name, values in scores.items()
        }

    def _carve_stopping_subset(self, X_fold, y_fold, fraction: float) -> tuple:
        """A fold's rows split into ``(X_fit, y_fit, X_stop, y_stop)``.

        The referee a standing-val family's fit needs, taken from inside
        the fold. Reusing the run's standing val split instead would let
        every fold stop against the same rows, and a fold score is only an
        out-of-sample number if nothing about the fit saw those rows.

        Temporal mode carves the chronological **tail** of the fold: a
        stopping criterion that has seen the future is the leak D9 exists
        to prevent, and the rows arrive in split order. Stratified mode
        carves a stratified random subset, anything else a plain random
        one - both on the trainer's seed, so folds reproduce.

        Known limitation: the carve is not group-aware, so under
        ``cv_mode="group"`` one group's rows can land on both sides of a
        fold's fit/stop boundary. Pass an explicit splitter and pre-grouped
        frames if that matters for the problem.
        """
        n_stop = min(max(1, round(len(X_fold) * fraction)), len(X_fold) - 1)
        if self.cv_mode == "temporal":
            cut = len(X_fold) - n_stop
            fit_rows, stop_rows = np.arange(cut), np.arange(cut, len(X_fold))
        else:
            stratify = y_fold if self.cv_mode == "stratified" else None
            fit_rows, stop_rows = train_test_split(
                np.arange(len(X_fold)),
                test_size=n_stop,
                random_state=self.seed,
                stratify=stratify,
            )
        return (
            X_fold.iloc[fit_rows],
            y_fold[fit_rows],
            X_fold.iloc[stop_rows],
            y_fold[stop_rows],
        )

    def fresh(self) -> "BaseTrainer":
        """An unfitted twin: same family, params, task, seed, features.

        The round trip through :meth:`spec` is the point - it is the same
        description :meth:`load` rebuilds a saved run from, so a fold's
        trainer cannot quietly differ from the one the run ships.
        """
        return type(self).from_spec(self.spec())

    def hyperparameter_tune(
        self,
        X: pd.DataFrame,
        y,
        n_trials: int = 100,
        cv: int | Any = 5,
        metric: str | None = None,
        direction: str = "maximize",
        **optuna_kwargs,
    ) -> dict:
        """Bayesian search over :meth:`_get_param_space`, scored by CV.

        A fresh model per trial, and the winners are folded into
        ``self.params`` so the next :meth:`train` builds with them - a
        search result must not be a thing the caller can forget to apply.

        Args:
            n_trials: Optuna trials.
            cv: Fold count (splitter follows ``cv_mode``) or a splitter.
            metric: sklearn scoring string; None -> the task default.
            direction: ``"maximize"`` or ``"minimize"``. Every default
                scoring string here is already higher-is-better (sklearn's
                ``neg_*`` convention), so the default is maximize.

        Returns:
            The best parameters found.

        Raises:
            ImportError: If optuna is not installed.
        """
        optuna = _import_optuna()
        metric = metric or TUNE_METRIC[self.task]
        splitter = self._splitter(cv)
        X_aligned = self.align(X)

        def objective(trial) -> float:
            resolved = self._get_param_space(trial)
            # study.best_params holds only what was *suggested*; a space that
            # derives a value from a suggestion (a solver's penalty, a width
            # to a layer list) would lose it. Record the resolved dict here
            # and read it back from the winning trial.
            trial.set_user_attr("resolved_params", resolved)
            scores = sk_cross_validate(
                self._cv_estimator(resolved),
                X_aligned,
                y,
                cv=splitter,
                scoring=metric,
                return_train_score=False,
            )
            return float(np.mean(scores["test_score"]))

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

    def _splitter(self, cv: int | Any):
        """A fold count follows ``cv_mode`` (D9); a splitter passes through."""
        return (
            make_cv_splitter(self.cv_mode, cv, self.seed) if isinstance(cv, int) else cv
        )

    def _cv_estimator(self, overrides: dict | None = None):
        """A fresh, unfitted, sklearn-compatible pipeline for the tuner.

        Preprocessing is *inside* it so every fold refits its own imputers
        and encoders - the leakage-as-architecture fix (D6). Trainers whose
        model is not sklearn-compatible override this and say so;
        :meth:`cross_validate` no longer needs it, because it runs the
        family's own procedure per fold instead.
        """
        model = self._build_model()
        if overrides:
            model.set_params(**overrides)
        return Pipeline([("preprocess", self.new_preprocessor()), ("model", model)])

    # -------------------------------------------------------------- shared

    def new_preprocessor(self):
        """An unfitted ``ColumnTransformer`` for this family's features."""
        return build_preprocessor(
            self.numeric_features,
            self.categorical_features,
            scale_numeric=self.scale_numeric,
        )

    @property
    def feature_columns(self) -> list[str]:
        """The exact input contract: which columns, in which order."""
        return [*self.numeric_features, *self.categorical_features]

    @property
    def model_type(self) -> str:
        """``metadata.json``'s ``model_type``, which is the family key."""
        return self.kind

    def get_params(self) -> dict:
        """Flat, loggable view of what this trainer is - tracker params."""
        params = {
            "trainer": self.kind,
            "task": self.task,
            "seed": self.seed,
            "cv_mode": self.cv_mode,
            "n_numeric_features": len(self.numeric_features),
            "n_categorical_features": len(self.categorical_features),
            "tuned": self.best_params is not None,
        }
        params.update({f"model_{k}": v for k, v in self.params.items()})
        return params

    def spec(self) -> dict:
        """The config round-trip: enough to rebuild an unfitted twin.

        Stored as ``metadata.json``'s ``hyperparameters``, which is what
        :meth:`load` reads back. ``model_class`` is the reload guard - a
        spec written by one trainer class must never be handed to another.
        Subclasses contribute their harness knobs through
        :meth:`extra_spec`.
        """
        return {
            "model_class": type(self).__name__,
            "trainer": self.kind,
            "params": self.params,
            "best_params": self.best_params,
            "task": self.task,
            "seed": self.seed,
            "cv_mode": self.cv_mode,
            "numeric_features": self.numeric_features,
            "categorical_features": self.categorical_features,
            "options": self.extra_spec(),
        }

    def extra_spec(self) -> dict:
        """Subclass constructor kwargs beyond the shared ones. Override."""
        return {}

    @classmethod
    def from_spec(cls, spec: dict) -> "BaseTrainer":
        """Rebuild an **unfitted** trainer from :meth:`spec` output.

        Raises:
            ValueError: If the spec was written by a different trainer
                class. Loading a LightGBM run into ``TorchTrainer`` would
                otherwise fail somewhere deep and unhelpful.
        """
        recorded = spec.get("model_class")
        if recorded is not None and recorded != cls.__name__:
            raise ValueError(
                f"Saved model class {recorded!r} does not match {cls.__name__!r}; "
                "the run was produced by a different trainer"
            )
        trainer = cls(
            params=spec.get("params", {}),
            task=spec.get("task", "classification"),
            seed=spec.get("seed", 42),
            numeric_features=spec.get("numeric_features", []),
            categorical_features=spec.get("categorical_features", []),
            cv_mode=spec.get("cv_mode", "stratified"),
            **spec.get("options", {}),
        )
        trainer.best_params = spec.get("best_params")
        return trainer

    def check_fitted(self) -> None:
        """Raise before an unfitted trainer produces plausible nonsense."""
        if not self.fitted:
            raise RuntimeError(
                f"{type(self).__name__} is not fitted; call train() (or load()) first"
            )

    def align(self, X: pd.DataFrame) -> pd.DataFrame:
        """Reindex a frame to the recorded feature contract.

        Every predict path goes through this rather than trusting the
        caller's column order: the preprocessor selects by name, but a
        positional array downstream (a tensor, a raw booster matrix) does
        not, and a silently reordered frame is a plausible wrong answer.
        """
        missing = [c for c in self.feature_columns if c not in X.columns]
        if missing:
            raise ValueError(
                f"Input is missing {len(missing)} feature column(s) the model "
                f"was trained on: {missing}"
            )
        return X[self.feature_columns]

    @staticmethod
    def read_spec(run_dir: str | Path) -> dict:
        """The metadata-first half of every ``load``: the recorded spec."""
        return load_metadata(run_dir)["hyperparameters"]

    @staticmethod
    def read_files(run_dir: str | Path) -> dict[str, str]:
        """The recorded ``files`` map - nothing guesses a filename."""
        return load_metadata(run_dir)["files"]
