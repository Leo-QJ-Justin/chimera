"""``BaseTrainer``: the one contract every model family is reached through.

The training pipeline builds a trainer from the ``trainer/`` config group
and then only ever calls the methods below. That is what keeps the
orchestrator free of ``if trainer.kind == ...`` branches, and what lets the
inference pipeline reload a torch run and a LightGBM run with identical
code.

The base is deliberately thin. It fixes the *contract* - which methods
exist and what they promise - plus the few services that must be identical
across families for their numbers to be comparable: ``cross_validate``
(the whole procedure goes inside the fold, R1.11), the stopping-subset
carve, the spec round-trip, and the shared tuning tables below. Everything
a family does to a model it writes in its own class body, ``evaluate`` and
``hyperparameter_tune`` included, so each trainer file reads top to bottom
without hopping up a hierarchy. Sibling duplication is the accepted price;
a family that cannot be read on its own is what it buys off.

Four decisions the rest of the file assumes:

- **Validation data is in ``train``'s signature**, not out-of-band state,
  because three shipped trainers need it during the fit (LightGBM and
  XGBoost early stopping, torch's per-epoch monitor). A trainer with no
  use for it ignores it - and says so through ``uses_val_in_fit``, the
  declaration the family's own ``fit_frames`` / ``evaluate_run`` /
  ``selection_key`` then act on (R1.10, R1.13) and which decides, inside
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
from typing import Any, ClassVar, NamedTuple

import numpy as np
import pandas as pd
from pydantic import ValidationError
from sklearn.model_selection import train_test_split

from ....core.run_artifacts import load_metadata
from ....schemas import ParamSpace
from ...evaluation_pipeline.modules.metrics import METRIC_DIRECTIONS
from ..modules.preprocessing import build_preprocessor
from ..modules.splitting import make_cv_splitter

logger = logging.getLogger(__name__)

# Tuning defaults per task: (project metric alias, optimisation direction).
# One table for every family, so what a tuned run optimises by default is a
# property of the task rather than of whichever trainer was selected.
TUNE_DEFAULT = {
    "classification": ("f1_macro", "maximize"),
    "regression": ("rmse", "minimize"),
}
# Share of the search frames a standing-val family carves off as the referee
# its trials early-stop against and are then scored on. Larger than
# CV_STOP_FRACTION because here the carve is also the *score*: one split
# decides the winner, so it has to be big enough to mean something.
TUNE_HOLDOUT_FRACTION = 0.2
# Share of each CV fold's training rows carved out as the early-stopping
# referee, for families whose fit needs one (R1.11). Matches the standing
# val split's share of the run, so a fold's fit is shaped like the real one.
CV_STOP_FRACTION = 0.15


class FitFrames(NamedTuple):
    """What one run's search and final fit are handed, per protocol.

    Returned by :meth:`BaseTrainer.fit_frames`, which is how the training
    pipeline shapes a run's data without knowing which family it got.
    """

    X_fit: pd.DataFrame
    y_fit: pd.Series
    # The standing referee an in-fit stopping criterion needs; None when the
    # family's fit reads none, so that a family which pooled those rows into
    # X_fit cannot also be handed them as a "validation split".
    X_ref: pd.DataFrame | None
    y_ref: pd.Series | None
    # What ``metadata.json`` records as ``fit_splits``: ["train"], or
    # ["train", "val"] for a family that pooled them.
    fit_splits: list[str]


def resolve_tune_metric(
    task: str, metric: str | None, direction: str | None
) -> tuple[str, str]:
    """``(metric, direction)`` for a search: what was asked, else the tables.

    Every family opens its ``hyperparameter_tune`` with this line, which is
    why it is a function rather than five copies of a lookup: it is data
    resolution, not part of any family's ML story.

    Args:
        task: ``"classification"`` or ``"regression"``.
        metric: A project metric alias, or None for the task default.
        direction: ``"maximize"``/``"minimize"``, or None to infer it from
            the metric.

    Raises:
        ValueError: If a direction has to be inferred for a metric that has
            none recorded. A custom metric may be optimised, but only with
            its direction said out loud - a search run the wrong way round
            still finishes and still writes a run.
    """
    default_metric, default_direction = TUNE_DEFAULT[task]
    if metric is None:
        return default_metric, direction or default_direction
    if direction is None and metric not in METRIC_DIRECTIONS:
        raise ValueError(
            f"No recorded direction for metric {metric!r}: name one of "
            f"{sorted(METRIC_DIRECTIONS)}, or set tune.direction explicitly"
        )
    return metric, direction or METRIC_DIRECTIONS[metric]


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
            The family's own protocol methods act on it (R1.10): True keeps
            val a standing referee outside the fit, False pools train+val
            and selects on a k-fold CV estimate. The orchestrator never
            reads it (R1.13); ``cross_validate`` does, to decide whether a
            fold carves its own stopping subset.
        TUNABLE: This family's search space - parameter name -> default
            range - declared in its own class body and overridable per run
            through ``trainer.tune.space``.
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
    # Same rule, same reason: what a family searches over is part of what the
    # family is, so there is nothing sensible here to inherit.
    TUNABLE: ClassVar[dict[str, ParamSpace]]

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
    def _get_param_space(self, trial, space: dict) -> dict:
        """One trial's parameters, suggested define-by-run from ``space``.

        Args:
            trial: The Optuna trial (duck-typed: only ``suggest_*`` is used).
            space: The merged table from :meth:`_merged_space`. A name absent
                from it must not be suggested at all - that is how
                ``tune.space: {<name>: false}`` takes a knob out of a search.

        Returns:
            The **resolved** parameters, derived values included (a solver's
            penalty, a width and a depth turned into a layer list). Optuna
            records only what it suggested, so this dict is what each
            family's tuner stores on the trial and reads back off the winner.
        """

    @abstractmethod
    def fit_frames(self, X: dict, y: dict) -> FitFrames:
        """The frames this family's search and final fit see (R1.13).

        How a run's data is shaped for the fit is family knowledge, so the
        orchestrator asks rather than branching on a flag: it makes one
        unconditional ``train(X_fit, y_fit, X_ref, y_ref)`` call and one
        tune call over the same fit frames, whichever family it was handed.

        Args:
            X: ``{"train"/"val"/"test": features}``, the realized split.
            y: The matching targets, under the same keys.

        Returns:
            A :class:`FitFrames`. ``X_fit`` holds exactly the rows of
            ``fit_splits``, **in split order** - the order is what lets a
            temporal run's CV fold carve its stopping subset off the end of
            its own training window. ``X_ref`` is None if and only if this
            family's fit consumes no standing referee, which must agree with
            what it declared through ``uses_val_in_fit``. Test is never
            touched.
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
    def evaluate(
        self, X: pd.DataFrame, y, metrics: list[str | Callable] | None = None
    ) -> dict[str, float]:
        """Score a frame with the project's metric definitions.

        Three lines every family writes identically (``check_fitted``, then
        ``compute_metrics`` over its own predictions) and none inherits: it
        is the measurement behind every number a run publishes, and it
        belongs in the file whose predictions it measures.

        Args:
            X: Features, in any column order (realigned internally).
            y: Ground truth.
            metrics: Metric names or callables; None -> the task defaults.
        """

    @abstractmethod
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
        """Every number this run publishes, in terms its protocol defends.

        What a run may claim follows from how it was fitted, so the family
        scores itself and the orchestrator only times the call and logs the
        result. It is handed the split frames, the frames the fit consumed,
        and the run's ``selection`` values as plain arguments - no config
        object and no tracker reach a trainer.

        Args:
            X: ``{"train"/"val"/"test": features}``, the realized split.
            y: The matching targets, under the same keys.
            X_fit: The frames the fit consumed (:meth:`fit_frames`).
            y_fit: The matching targets.
            metric: ``selection.metric``, a project metric alias.
            cv: Fold count for a CV estimate - the run's ``trainer.tune.cv``,
                which is its declared CV budget whether or not a search ran.
            basis: ``selection.basis`` (``auto`` | ``cv``).
            split: ``selection.split``. In the signature because both
                protocols name it in the line they log about it.

        Returns:
            ``{metric key: value}``, containing the key
            :meth:`selection_key` names for the same arguments. ``test_*``
            is scored exactly once, and a family whose fit consumed val
            publishes no ``val_*``: a metric labelled "val" is read as
            held-out, and the label is why anyone trusts the number.
        """

    @abstractmethod
    def selection_key(self, *, metric: str, basis: str, split: str) -> tuple[str, str]:
        """``(basis, metric key)`` - what ``best.json`` means for this run.

        Pure, and callable on an unfitted trainer: the tracker params, the
        metadata envelope and the pointer all name the basis, and none of
        them should have to wait for a model to exist to find out what it is.

        Returns:
            The recorded ``selection_basis`` and the key of the number the
            pointer ranks on - which :meth:`evaluate_run` publishes for the
            same arguments. The key's prefix is what stops two kinds of
            estimate from being silently ranked against each other.
        """

    @abstractmethod
    def hyperparameter_tune(
        self,
        X: pd.DataFrame,
        y,
        n_trials: int = 100,
        cv: int | Any = 5,
        metric: str | None = None,
        direction: str | None = None,
        space: dict | None = None,
        **kwargs,
    ) -> dict:
        """Search this family's own space; the family owns the whole search.

        Abstract, and abstract *only*: there is no shared sweeper to inherit
        and no hook to fill in. A family scores its trials by the procedure
        it actually ships - a pooled family through :meth:`cross_validate`,
        a standing-val family on a carved holdout its trials early-stop
        against - and nothing obliges the next family to use Optuna at all.
        What the base fixes is this signature and the postconditions below,
        which is all the training pipeline calls.

        Args:
            n_trials: Search budget, in trials.
            cv: Fold count (the splitter follows ``cv_mode``, per D9) or an
                explicit splitter, for a family that scores a trial by
                cross-validation. A family that scores a trial on a holdout
                ignores it, and says so.
            metric: A *project metric alias* - the vocabulary
                :meth:`evaluate` speaks, never a sklearn scoring string.
                None -> ``TUNE_DEFAULT[task]``.
            direction: ``"maximize"``/``"minimize"``; None -> inferred from
                the metric (:func:`resolve_tune_metric`).
            space: ``trainer.tune.space`` - per-parameter overrides of this
                family's ``TUNABLE``, merged by :meth:`_merged_space`.

        Returns:
            The best parameters found. The same dict must be left on
            ``self.best_params`` and folded into this trainer's own config,
            so the next :meth:`train` builds with them - a search result is
            not something the caller can be trusted to remember to apply.
        """

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
        out-of-sample number if nothing about the fit saw those rows. The
        same carve is what gives such a family's *search* the per-trial
        referee its trials early-stop against and are then scored on.

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

    def _merged_space(self, overrides: dict | None = None) -> dict[str, ParamSpace]:
        """This family's ``TUNABLE`` table with a config's overrides applied.

        The one piece of tuning machinery that is shared, because it is the
        *config contract* rather than anyone's search: a range typed into
        ``trainer.tune.space`` has to mean the same thing whichever family
        reads it.

        Three behaviours, in the order a config meets them:

        - ``false`` drops the name from the search entirely. Nothing
          special-cases it afterwards - the parameter simply keeps whatever
          ``params`` says, exactly as on an untuned run.
        - A range is merged **field-wise onto the declared one and
          re-validated as the declared kind**, so overriding ``low``/``high``
          keeps a declared ``log: true`` instead of silently resetting it,
          and a list of choices written over a numeric range fails loudly
          rather than half-applying.
        - An unrecognised name raises, listing what this family does tune. A
          typo there would otherwise read as configured and search as if it
          were not.

        Raises:
            ValueError: On an unknown parameter name, or an override that
                cannot be read as the declared kind of range.
        """
        merged = dict(type(self).TUNABLE)
        for name, override in (overrides or {}).items():
            if name not in merged:
                raise ValueError(
                    f"tune.space names {name!r}, which {type(self).__name__} does "
                    f"not tune; its tunables are {sorted(merged)}"
                )
            if override is False:
                merged.pop(name)
                continue
            declared = merged[name]
            kind = type(declared)
            # exclude_unset so an override says only what it meant to say: a
            # full dump would carry the override's own defaults along with it
            # and overwrite fields the config never mentioned.
            fields = {**declared.model_dump(), **override.model_dump(exclude_unset=True)}
            try:
                merged[name] = kind(**fields)
            except ValidationError as e:
                raise ValueError(
                    f"tune.space.{name} is not a valid {kind.__name__}, which is "
                    f"how {type(self).__name__} declares it: {e}"
                ) from e
        return merged

    def _splitter(self, cv: int | Any):
        """A fold count follows ``cv_mode`` (D9); a splitter passes through."""
        return (
            make_cv_splitter(self.cv_mode, cv, self.seed) if isinstance(cv, int) else cv
        )

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
