"""Composite pydantic schemas for the four pipelines.

Hydra composes the config files; these models validate what came out.
Every section subclasses a base in ``core.config`` so cross-pipeline
sections (logging, mlflow, split) stay one definition - the mistake this
avoids is the corpus pattern where one pipeline re-declared its own
``LoggingConfig`` as a bare ``BaseModel`` and drifted.

Custom validators here express only what pydantic cannot: cross-field
rules (feature lists must not contain the target, temporal splits need a
time column and boundaries, a selection metric must exist for the
configured task). Type and range checks stay declarative.

``bootstrap`` at the bottom is what every ``run_*.py`` calls: validate,
configure logging once, report defaults. Nothing else in the project may
configure logging.
"""

import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .core.config import (
    LoggingConfig,
    MlflowConfig,
    RunConfig,
    SplitConfig,
    log_config_defaults,
    to_plain_dict,
    warn_extra_sections,
)
from .core.logging_setup import configure_logging

logger = logging.getLogger(__name__)

# Kept in step with evaluation_pipeline/modules/metrics.py, which is the one
# place metrics are computed. A selection metric the run cannot produce is a
# config error, and it is caught here rather than at pointer-update time.
CLASSIFICATION_METRICS = ("accuracy", "f1_macro")
REGRESSION_METRICS = ("rmse", "mae", "r2")

Task = Literal["classification", "regression"]

# The data pipeline's stage boundaries, in order. Any of them can be piped
# out to disk via `checkpoints`; the last one's output is `processed_path`.
STAGE_NAMES = ("raw", "cleaned", "features")


# ------------------------------------------------------------ shared sections


class ProjectLoggingConfig(LoggingConfig):
    """Adds the dictConfig escape hatch to the core logging section."""

    # None -> programmatic console (+ file) logger; a path -> dictConfig.
    config_path: str | None = None


class MonitorConfig(BaseModel):
    """The single monitored metric for iterative trainers: "better", named once."""

    model_config = {"extra": "ignore"}

    # Any key the epoch emits: train_loss | val_loss | train_metric |
    # val_metric | lr.
    name: str = "val_loss"
    mode: Literal["min", "max"] = "min"


class TorchTrainerConfig(BaseModel):
    """Harness knobs for ``TorchTrainer`` - the loop, not the architecture.

    Architecture lives in ``TrainerConfig.params`` because it decides the
    shapes a checkpoint carries; everything here decides what the loop does
    with them.
    """

    model_config = {"extra": "ignore"}

    lr: float = 1e-3
    weight_decay: float = 0.0
    epochs: int = Field(default=30, ge=1)
    batch_size: int = 32
    patience: int = 5
    monitor: MonitorConfig = MonitorConfig()
    lr_factor: float = 0.5
    lr_patience: int = 2
    min_lr: float = 1e-6
    # Resume is a named product choice, not an implied behaviour.
    resume: Literal["continue", "from_best"] = "continue"
    resume_from: str | None = None
    # Fraction of the training split drawn per epoch; 0 would train on nothing.
    subsample_frac: float = Field(default=1.0, gt=0.0, le=1.0)
    sanity_check: bool = False
    num_workers: int = 0
    pin_memory: bool = False
    device: str = "auto"
    visible_devices: str | None = None
    device_order: str = "PCI_BUS_ID"
    deterministic_cudnn: bool = False

    @field_validator("visible_devices", mode="before")
    @classmethod
    def coerce_device_list(cls, value):
        """Accept ``visible_devices=0`` from the CLI, not just ``"0"``.

        Hydra types a bare ``0`` as an int and ``0,1`` as a string; both end
        up in the same environment variable.
        """
        return None if value is None else str(value)


class BoosterConfig(BaseModel):
    """Early-stopping knobs for the boosters (LightGBM, XGBoost).

    One class for both: the two families differ in how early stopping is
    wired into the fit, not in what the analyst has to decide about it.
    """

    model_config = {"extra": "ignore"}

    # None -> no early stopping; train the full n_estimators.
    early_stopping_rounds: int | None = 50
    log_period: int = 0


class IntSpace(BaseModel):
    """An integer range in a search space: ``{low, high, step, log}``."""

    # Forbidden rather than ignored, unlike the composite sections above: a
    # range is typed by hand into a trainer file, nothing composes extra keys
    # into it, and it is what makes the ParamSpace union deterministic -
    # `choices` can only ever be a ChoiceSpace.
    model_config = {"extra": "forbid"}

    low: int
    high: int
    step: int = 1
    log: bool = False

    @model_validator(mode="after")
    def validate_log_scale(self):
        """Optuna rejects a log-scaled integer range with a step; say so here."""
        if self.log and self.step != 1:
            raise ValueError(
                f"log=true cannot be combined with step={self.step}: a "
                "log-scaled integer range is sampled one value at a time"
            )
        return self

    def suggest(self, trial, name: str):
        """One value from this range, from an Optuna trial (duck-typed)."""
        return trial.suggest_int(name, self.low, self.high, step=self.step, log=self.log)


class FloatSpace(BaseModel):
    """A float range in a search space: ``{low, high, step, log}``."""

    model_config = {"extra": "forbid"}

    low: float
    high: float
    # None -> continuous. A step and a log scale are mutually exclusive,
    # which Optuna itself says at suggest time.
    step: float | None = None
    log: bool = False

    def suggest(self, trial, name: str):
        """One value from this range, from an Optuna trial (duck-typed)."""
        return trial.suggest_float(
            name, self.low, self.high, step=self.step, log=self.log
        )


class ChoiceSpace(BaseModel):
    """An explicit list of candidate values, sampled categorically."""

    model_config = {"extra": "forbid"}

    # Untyped on purpose: a categorical range is a mix of strings, numbers
    # and None as often as not ("sqrt" | "log2" | null for max_features).
    choices: list

    def suggest(self, trial, name: str):
        """One value from this list, from an Optuna trial (duck-typed)."""
        return trial.suggest_categorical(name, self.choices)


# What one entry of `tune.space` may be. The trial is duck-typed through
# `suggest`, so nothing here imports optuna: a search space is config, and
# config must validate on a machine that never installed the 'tune' extra.
ParamSpace = IntSpace | FloatSpace | ChoiceSpace


class TuneConfig(BaseModel):
    """Optuna search, declared per trainer rather than per run.

    Off by default: a tuned run costs ``n_trials * cv`` fits, and turning
    that on should be a visible choice in the trainer's own file.
    """

    model_config = {"extra": "ignore"}

    enabled: bool = False
    n_trials: int = 20
    # Folds for the tuning CV. The *splitter* comes from split.mode (D9),
    # never a hardcoded TimeSeriesSplit. Families whose fit needs a stopping
    # referee score their trials on a carved holdout instead and ignore this.
    cv: int = 3
    # A *project metric alias* - the same vocabulary evaluate() and the
    # evaluation report speak: "f1_macro", "accuracy", "rmse", "mae", "r2".
    # Never a sklearn scoring string. None -> the task default.
    metric: str | None = None
    # None -> inferred from the metric (error-like metrics minimize, the rest
    # maximize), so `metric: rmse` left alone cannot silently search for the
    # worst model.
    direction: Literal["maximize", "minimize"] | None = None
    # Per-parameter overrides of the family's own TUNABLE table: a range to
    # narrow or widen one, `false` to drop the name from the search entirely
    # (its `params` value then stands, as it does on an untuned run). A name
    # the family does not tune raises, listing the ones it does.
    space: dict[str, ParamSpace | Literal[False]] = {}


class TrainerConfig(BaseModel):
    """One entry of the ``trainer/`` config group.

    ``kind`` **is** the family: it names the trainer class, the config
    group file, and ``model_type`` in the saved metadata. ``params`` are
    that family's own estimator kwargs. The per-family sections below carry
    harness knobs only one trainer reads; an unused section costs nothing
    and keeps ``trainer=<kind>`` a single-file swap.
    """

    model_config = {"extra": "ignore", "protected_namespaces": ()}

    kind: Literal["logreg", "random_forest", "lightgbm", "xgboost", "torch"] = "logreg"
    # Free-form: each family has its own knobs, and the trainer passes them
    # straight through so a typo raises in the constructor, loudly.
    params: dict = {}
    tune: TuneConfig = TuneConfig()
    torch: TorchTrainerConfig = TorchTrainerConfig()
    lightgbm: BoosterConfig = BoosterConfig()
    xgboost: BoosterConfig = BoosterConfig()


# ---------------------------------------------------------------- data pipeline


class CleaningConfig(BaseModel):
    """Knobs for the STATELESS cleaning stage (nothing here may ``.fit()``)."""

    model_config = {"extra": "ignore"}

    sentinel_values: list = []
    drop_duplicates: bool = True
    dedup_subset: list[str] | None = None
    drop_rows_missing: list[str] = []
    strip_whitespace: bool = True


class FeatureEngineeringConfig(BaseModel):
    """Knobs for the STATELESS feature stage."""

    model_config = {"extra": "ignore"}

    date_parts: bool = True
    drop_columns: list[str] = []


class DataPipelineConfig(RunConfig):
    """load -> clean -> engineer -> model-input table (never splits, never fits)."""

    model_config = {"extra": "ignore"}

    raw_path: str = "data/raw/dataset.csv"
    # The final stage's output: the only file the training pipeline reads.
    processed_path: str = "data/processed/model_input.parquet"
    # Stage boundaries to pipe out for inspection, from STAGE_NAMES. Purely
    # diagnostic - nothing downstream reads them, so adding or dropping one
    # changes no contract.
    checkpoints: list[str] = []
    checkpoint_dir: str = "data/processed"
    key_cols: list[str] = ["entity_id", "date"]
    date_col: str | None = "date"
    target: str = "target"
    cleaning: CleaningConfig = CleaningConfig()
    features: FeatureEngineeringConfig = FeatureEngineeringConfig()
    logging: ProjectLoggingConfig = ProjectLoggingConfig()
    mlflow: MlflowConfig = MlflowConfig()

    @model_validator(mode="after")
    def validate_keys_survive(self):
        """The model-input table must keep its split keys and its label.

        Cross-field, so pydantic cannot express it: ``features.drop_columns``
        is only wrong relative to ``key_cols``/``target``.
        """
        if not self.key_cols:
            raise ValueError(
                "key_cols must not be empty: split membership is recorded by "
                "stable keys, never by positional index"
            )
        dropped = set(self.features.drop_columns)
        clobbered = sorted(dropped & (set(self.key_cols) | {self.target}))
        if clobbered:
            raise ValueError(
                f"features.drop_columns removes columns the model-input table must "
                f"carry: {clobbered}"
            )
        if Path(self.raw_path) == Path(self.processed_path):
            raise ValueError("processed_path must differ from raw_path")
        unknown = sorted(set(self.checkpoints) - set(STAGE_NAMES))
        if unknown:
            raise ValueError(
                f"checkpoints names unknown stages {unknown}; the data pipeline "
                f"has stages {list(STAGE_NAMES)}"
            )
        return self


# ------------------------------------------------------------ training pipeline


class TrainingSplitConfig(SplitConfig):
    """Core split protocol plus the temporal-mode time column."""

    time_col: str | None = None

    @model_validator(mode="after")
    def validate_temporal_inputs(self):
        if self.mode != "temporal":
            return self
        if not self.time_col:
            raise ValueError("split.mode='temporal' requires split.time_col")
        missing = {"val_start", "test_start"} - set(self.boundaries)
        if missing:
            raise ValueError(
                f"split.mode='temporal' requires boundaries {sorted(missing)}"
            )
        return self


class SelectionConfig(BaseModel):
    """What ``best.json`` means for this project."""

    model_config = {"extra": "ignore"}

    # Validated against the task in TrainingConfig: a metric the run never
    # emits would fail at pointer-update time, after the fit.
    metric: str = "f1_macro"
    mode: Literal["min", "max"] = "max"
    split: Literal["val", "test"] = "val"
    # Which number best.json records (R1.11). "auto": each family's own
    # protocol decides - a standing-val family selects on `split`, a pooled
    # one on its CV estimate, and the two are deliberately not rankable
    # against each other. "cv": every family selects on a procedure-CV
    # estimate over train+val, which is the one yardstick runs of different
    # families can be ranked on - at the cost of k extra fits for a
    # standing-val family, whose train_/val_/test_ metrics are unchanged.
    basis: Literal["auto", "cv"] = "auto"


class ShapConfig(BaseModel):
    """SHAP attributions over a sample of the validation design matrix.

    Sampled rather than exhaustive: an exact explainer is superlinear in
    rows, and the beeswarm of 200 rows says what the beeswarm of 20,000
    says. Needs the optional ``explain`` extra; without it the step logs
    one line and is skipped.
    """

    model_config = {"extra": "ignore"}

    enabled: bool = True
    sample_size: int = Field(default=200, ge=1)
    max_display: int = Field(default=20, ge=1)


class DiagnosticsConfig(BaseModel):
    """Post-fit figures drawn from the fitted model itself.

    Model-based, which is why they belong to the training pipeline:
    curves come from the family's own per-iteration history, importances
    and SHAP from the estimator's internals. Prediction-based figures
    (confusion matrix, ROC, calibration, residuals) belong to the
    evaluation pipeline, which is where the predictions are.
    """

    model_config = {"extra": "ignore"}

    enabled: bool = True
    shap: ShapConfig = ShapConfig()


class TrainingConfig(RunConfig):
    """processed -> split -> trainer.fit -> trainer.evaluate -> run directory."""

    model_config = {"extra": "ignore"}

    processed_path: str = "data/processed/model_input.parquet"
    output_dir: str = "outputs/training"
    task: Task = "classification"
    target: str = "target"
    key_cols: list[str] = ["entity_id", "date"]
    numeric_features: list[str] = []
    categorical_features: list[str] = []
    trainer: TrainerConfig = TrainerConfig()
    split: TrainingSplitConfig = TrainingSplitConfig()
    selection: SelectionConfig = SelectionConfig()
    diagnostics: DiagnosticsConfig = DiagnosticsConfig()
    logging: ProjectLoggingConfig = ProjectLoggingConfig()
    mlflow: MlflowConfig = MlflowConfig()

    @model_validator(mode="after")
    def validate_feature_declaration(self):
        """Target-leak and double-declaration guards, plus key inheritance."""
        overlap = sorted(set(self.numeric_features) & set(self.categorical_features))
        if overlap:
            raise ValueError(f"columns declared numeric and categorical: {overlap}")
        declared = set(self.numeric_features) | set(self.categorical_features)
        if self.target in declared:
            raise ValueError(
                f"target {self.target!r} is declared as a feature - that is "
                "label leakage, not a feature set"
            )
        leaked_keys = sorted(declared & set(self.key_cols))
        if leaked_keys:
            logger.warning(
                "Key columns %s are also declared as features; they identify "
                "rows, so check this is deliberate",
                leaked_keys,
            )
        if not self.split.key_cols:
            # Fill rather than fail: one key list per project is the norm.
            self.split.key_cols = list(self.key_cols)
            logger.warning(
                "split.key_cols was empty; inherited key_cols=%s", self.key_cols
            )
        return self

    @model_validator(mode="after")
    def validate_task_agreement(self):
        """The selection metric and the split mode must suit the task."""
        check_metric(self.selection.metric, self.task, "selection.metric")
        if self.trainer.tune.metric is not None:
            # Same vocabulary as selection.metric, checked for the same
            # reason - and it also catches a sklearn scoring string left over
            # from a config written against an older tuner.
            check_metric(self.trainer.tune.metric, self.task, "trainer.tune.metric")
        if self.task == "regression" and self.split.mode == "stratified":
            # sklearn's own error for this ("least populated class has 1
            # member") names every distinct target value and explains nothing.
            raise ValueError(
                "split.mode='stratified' needs a categorical target; use "
                "'shuffle' or 'temporal' for task='regression'"
            )
        return self


# ----------------------------------------------------------- inference pipeline


class ModelSelectionConfig(BaseModel):
    """Which trained run to serve."""

    model_config = {"extra": "ignore"}

    use: Literal["best", "latest"] = "best"
    timestamp: str | None = None
    runs_dir: str = "outputs/training"

    @field_validator("timestamp", mode="before")
    @classmethod
    def reject_unquoted_timestamp(cls, value):
        """Catch ``model.timestamp=20260730_143000`` typed without quotes.

        Hydra reads the underscore as a digit separator, so the value
        arrives as an int with the separator already gone. Coercing it back
        to a string would silently look for the wrong run.
        """
        if isinstance(value, int):
            raise ValueError(
                f"model.timestamp arrived as the integer {value}: Hydra read "
                "the underscore as a digit separator. Quote it: "
                "model.timestamp='20260730_143000'"
            )
        return value


class InferenceConfig(RunConfig):
    """Metadata-first reload + the same sample path training used (D4)."""

    model_config = {"extra": "ignore"}

    model: ModelSelectionConfig = ModelSelectionConfig()
    input_path: str = "data/processed/model_input.parquet"
    output_path: str = "outputs/inference/predictions.parquet"
    key_cols: list[str] = ["entity_id", "date"]
    include_probabilities: bool = True
    logging: ProjectLoggingConfig = ProjectLoggingConfig()
    mlflow: MlflowConfig = MlflowConfig()

    @model_validator(mode="after")
    def validate_output_and_selection(self):
        suffix = Path(self.output_path).suffix
        if suffix not in (".parquet", ".csv"):
            raise ValueError(f"output_path must end in .parquet or .csv, got {suffix!r}")
        if self.model.timestamp:
            logger.warning(
                "model.timestamp=%s is set, so model.use=%r is ignored",
                self.model.timestamp,
                self.model.use,
            )
        return self


# ---------------------------------------------------------- evaluation pipeline


class TriageConfig(BaseModel):
    """How many bad rows to surface, and what to show beside them."""

    model_config = {"extra": "ignore"}

    top_n: int = Field(default=20, ge=0)
    drill_down_columns: list[str] = []


class PlotsConfig(BaseModel):
    """Prediction-based figures for the evaluation report.

    Drawn from the predictions table alone (no model, no features), which
    is what keeps them on this side of the D4 boundary. ROC, PR and
    calibration additionally need the ``proba_*`` columns inference writes
    when ``include_probabilities`` is on; without them the confusion
    matrix is still drawn and a log line says why the rest were not.
    """

    model_config = {"extra": "ignore"}

    enabled: bool = True


class EvaluationConfig(RunConfig):
    """predictions + ground truth -> metrics report + error triage.

    Deliberately has no model, no feature list and no preprocessing: this
    pipeline consumes what inference produced (D4). If it ever needs to
    *build* a sample, that is the bug the one-data-path rule prevents.
    """

    model_config = {"extra": "ignore"}

    predictions_path: str = "outputs/inference/predictions.parquet"
    processed_path: str = "data/processed/model_input.parquet"
    output_dir: str = "outputs/evaluation"
    task: Task = "classification"
    target: str = "target"
    prediction_col: str = "prediction"
    key_cols: list[str] = ["entity_id", "date"]
    triage: TriageConfig = TriageConfig()
    plots: PlotsConfig = PlotsConfig()
    compare_to_best: bool = True
    runs_dir: str = "outputs/training"
    selection_metric: str = "f1_macro"
    logging: ProjectLoggingConfig = ProjectLoggingConfig()
    mlflow: MlflowConfig = MlflowConfig()

    @model_validator(mode="after")
    def validate_join_and_metric(self):
        if not self.key_cols:
            raise ValueError(
                "key_cols must not be empty: predictions are joined to ground "
                "truth by key, never by row position (the two files are "
                "written by different runs and need not share an order)"
            )
        check_metric(self.selection_metric, self.task, "selection_metric")
        return self


# --------------------------------------------------------------- entry helper


def metric_names(task: str) -> tuple[str, ...]:
    """Metric keys the metrics module produces for a task."""
    return CLASSIFICATION_METRICS if task == "classification" else REGRESSION_METRICS


def check_metric(metric: str, task: str, field: str) -> None:
    """Reject a selection metric the run will never emit.

    Two configs select a run by metric (training's ``best.json``,
    evaluation's comparison); both would otherwise fail *after* the work,
    at pointer-update time.

    Raises:
        ValueError: If ``metric`` is not produced for ``task``.
    """
    allowed = metric_names(task)
    if metric not in allowed:
        raise ValueError(
            f"{field}={metric!r} is not produced for task={task!r}; "
            f"choose from {list(allowed)}"
        )


def bootstrap(cfg, schema_cls: type[BaseModel]):
    """Validate a composed Hydra config and configure logging, once.

    Coerce to a plain dict, surface sections the schema ignores, validate,
    start logging, then report which values came from defaults - in that
    order, because the defaults report is useless before handlers exist.

    Args:
        cfg: The ``DictConfig`` handed over by ``@hydra.main``.
        schema_cls: The pipeline's composite schema.

    Returns:
        ``(config, log_path)`` - the validated model and the log file to
        upload as a run artifact (None when file logging is off).
    """
    raw = to_plain_dict(cfg)
    warn_extra_sections(schema_cls, raw)
    config = schema_cls(**raw)

    log_cfg = config.logging
    # __name__ is "<package>.schemas", so the package logger name follows the
    # scaffold rename with no edit.
    package = __name__.split(".")[0]
    log_path = configure_logging(
        package=package,
        level=getattr(logging, log_cfg.level.upper(), logging.INFO),
        log_dir=log_cfg.log_dir if log_cfg.log_to_file else None,
        log_prefix=log_cfg.log_prefix,
        tz=log_cfg.timezone,
        config_path=log_cfg.config_path,
    )
    log_config_defaults(config, prefix=f"{schema_cls.__name__}.")
    return config, log_path
