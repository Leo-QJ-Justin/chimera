"""``BaseTrainer``: the one contract every model family is reached through.

The training pipeline builds a trainer from the ``trainer/`` config group
and then only ever calls the methods below. That is what keeps the
orchestrator free of ``if trainer.name == ...`` branches, and what lets
the inference pipeline reload a torch run and a LightGBM run with
identical code.

**Two abstract hooks, three concrete services.** Subclasses implement
``_build_model`` (a fresh, seeded, unfitted estimator) and
``_get_param_space`` (the Optuna search space) plus ``train``/``predict``.
In exchange the base gives them ``evaluate``, ``cross_validate`` and
``hyperparameter_tune`` for free - which is the point: those three are
exactly where per-family reimplementations drift apart.

The contract, and the reason for each part:

``train(X, y, X_val, y_val)``
    Validation data is in the *signature*, not optional out-of-band
    state, because two of the three shipped trainers need it during the
    fit (LightGBM's ``eval_set`` early stopping, torch's per-epoch
    monitor). A trainer that has no use for it ignores it.

``predict`` / ``predict_proba``
    ``predict_proba`` is optional (base returns None): not every
    estimator has one, and the inference pipeline degrades to hard
    predictions rather than requiring every family to fake probabilities.

``evaluate(X, y, metrics=...)``
    Concrete, so no family can quietly score itself with its own metric
    definition. Names resolve through the project's alias table first
    (``f1_macro`` means one thing forever), then ``sklearn.metrics``;
    callables are accepted for anything neither covers.

``cross_validate(X, y, cv, metrics)``
    A **fresh** model per fold, always - reusing a fitted estimator
    across folds is leakage with extra steps. The splitter comes from the
    run's ``split.mode`` (D9), never a hardcoded ``TimeSeriesSplit``.

``hyperparameter_tune(...)``
    The Optuna loop, with a fresh model per trial. Optuna is an optional
    dependency; the import is guarded so a project that never tunes never
    installs it.

``save(run_dir) -> files map`` / ``load(run_dir)``
    **One-artifact rule.** ``save`` returns the ``{kind: filename}`` map
    that goes verbatim into ``metadata.json``, so nothing downstream ever
    globs a directory or guesses a filename. ``load`` is
    **metadata-first**: it reads ``metadata.json``, checks the recorded
    ``model_class`` against itself, rebuilds the trainer from the spec
    recorded there, then loads weights. Config files are not consulted -
    they may have moved on since the run.

``get_params()`` / ``spec()``
    ``get_params`` is the flat, loggable view (tracker params).
    ``spec`` is the **config round-trip**: everything needed to rebuild an
    equivalent, unfitted trainer. Keeping them separate is deliberate -
    the tracker wants ``model_lr=0.001``, the reload path wants a nested
    structure it can hand back to ``__init__``.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from sklearn.model_selection import cross_validate as sk_cross_validate
from sklearn.pipeline import Pipeline

from ....core.run_artifacts import load_metadata
from ...evaluation_pipeline.modules.metrics import compute_metrics
from ..modules.preprocessing import build_preprocessor
from ..modules.splitting import make_cv_splitter

logger = logging.getLogger(__name__)

# sklearn *scoring* strings (not metric-function names) for CV and tuning.
CV_SCORING = {
    "classification": ["accuracy", "f1_macro"],
    "regression": ["neg_root_mean_squared_error", "neg_mean_absolute_error", "r2"],
}
TUNE_METRIC = {"classification": "f1_macro", "regression": "neg_root_mean_squared_error"}


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
        name: Estimator or architecture name within this trainer.
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
        kind: Registry key, and the prefix of ``model_type`` in metadata
            (``"sklearn:logreg"``, ``"torch:mlp"``).
        best_params: Set by :meth:`hyperparameter_tune`; folded into
            ``params`` so the next ``train`` uses them.
        history: Per-iteration records for trainers that have iterations.
    """

    kind: ClassVar[str] = ""

    def __init__(
        self,
        name: str,
        params: dict | None = None,
        *,
        task: str = "classification",
        seed: int = 42,
        numeric_features: list[str] | None = None,
        categorical_features: list[str] | None = None,
        cv_mode: str = "stratified",
    ):
        self.name = name
        self.params = dict(params or {})
        self.task = task
        self.seed = seed
        self.numeric_features = list(numeric_features or [])
        self.categorical_features = list(categorical_features or [])
        self.cv_mode = cv_mode
        self.best_params: dict | None = None
        self.fitted = False
        # The fitted artifact. Deliberately NOT built in __init__ (unlike
        # the reference implementation): a torch module needs the design
        # matrix width, which only exists once data has been transformed.
        self.model: Any = None
        # Per-iteration records for trainers that have iterations (epochs,
        # boosting rounds). The orchestrator replays them into the tracker
        # after training, which is why train() needs no tracker argument and
        # the trainers stay free of tracking code.
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
        """The Optuna search space for this family.

        Args:
            trial: An ``optuna.Trial``.

        Returns:
            Parameter name -> suggested value.
        """

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
            Filenames only, never paths - the run dir is what resolves
            them, and it moves.
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

    # -------------------------------------------------- concrete services

    def evaluate(
        self, X: pd.DataFrame, y, metrics: list[str | Callable] | None = None
    ) -> dict[str, float]:
        """Score a frame with the project's metric definitions.

        Args:
            X: Features, in any column order (realigned internally).
            y: Ground truth.
            metrics: Metric names or callables; None -> the task defaults.

        Returns:
            Metric name -> value.
        """
        self.check_fitted()
        return compute_metrics(y, self.predict(X), task=self.task, metrics=metrics)

    def cross_validate(
        self, X: pd.DataFrame, y, cv: int | Any = 5, metrics: list[str] | None = None
    ) -> dict[str, dict[str, float]]:
        """Cross-validate a **fresh** model per fold.

        Args:
            X: Features.
            y: Target.
            cv: Fold count (the splitter then follows ``cv_mode``, per D9)
                or an explicit sklearn splitter.
            metrics: sklearn *scoring* strings; None -> the task defaults.

        Returns:
            ``{scoring_name: {"mean": ..., "std": ...}}``.
        """
        metrics = metrics or CV_SCORING[self.task]
        splitter = (
            make_cv_splitter(self.cv_mode, cv, self.seed) if isinstance(cv, int) else cv
        )
        results = sk_cross_validate(
            self._cv_estimator(),
            self.align(X),
            y,
            cv=splitter,
            scoring=metrics,
            return_train_score=False,
        )
        logger.info("Cross-validated %s over %s", self.model_type, splitter)
        return {
            metric: {
                "mean": float(np.mean(results[f"test_{metric}"])),
                "std": float(np.std(results[f"test_{metric}"])),
            }
            for metric in metrics
        }

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

        A fresh model per trial, and the winning params are folded into
        ``self.params`` so the next :meth:`train` builds with them - the
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
        splitter = (
            make_cv_splitter(self.cv_mode, cv, self.seed) if isinstance(cv, int) else cv
        )
        X_aligned = self.align(X)

        def objective(trial) -> float:
            candidate = self._cv_estimator(self._get_param_space(trial))
            scores = sk_cross_validate(
                candidate,
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

        self.best_params = dict(study.best_params)
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

    def _cv_estimator(self, overrides: dict | None = None):
        """A fresh, unfitted, sklearn-compatible pipeline for CV/tuning.

        Preprocessing is *inside* it so every fold refits its own imputers
        and encoders - the leakage-as-architecture fix (D6). Trainers whose
        model is not sklearn-compatible override this and say so.
        """
        model = self._build_model()
        if overrides:
            model.set_params(**overrides)
        return Pipeline(
            [
                (
                    "preprocess",
                    build_preprocessor(self.numeric_features, self.categorical_features),
                ),
                ("model", model),
            ]
        )

    # -------------------------------------------------------------- shared

    @property
    def feature_columns(self) -> list[str]:
        """The exact input contract: which columns, in which order."""
        return [*self.numeric_features, *self.categorical_features]

    @property
    def model_type(self) -> str:
        """``metadata.json``'s ``model_type``: ``"<kind>:<name>"``."""
        return f"{self.kind}:{self.name}"

    def get_params(self) -> dict:
        """Flat, loggable view of what this trainer is - tracker params."""
        params = {
            "trainer": self.kind,
            "model_name": self.name,
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
        :meth:`load` reads back. ``model_class`` is the reload guard:
        a spec written by one trainer class must never be handed to
        another. Subclasses contribute their harness knobs through
        :meth:`extra_spec`.
        """
        return {
            "model_class": type(self).__name__,
            "trainer": self.kind,
            "name": self.name,
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
            name=spec["name"],
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
