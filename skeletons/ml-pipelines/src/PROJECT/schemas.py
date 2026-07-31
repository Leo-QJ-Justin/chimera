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

from pydantic import BaseModel, field_validator, model_validator

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

    Architecture lives in ``TrainerConfig.params`` (it decides the shapes a
    checkpoint carries); everything here decides what the loop does with
    them. Splitting the two is what lets ``trainer=<other_arch>`` change one
    section and leave the harness alone.
    """

    model_config = {"extra": "ignore"}

    lr: float = 1e-3
    weight_decay: float = 0.0
    epochs: int = 30
    batch_size: int = 32
    patience: int = 5
    monitor: MonitorConfig = MonitorConfig()
    lr_factor: float = 0.5
    lr_patience: int = 2
    min_lr: float = 1e-6
    # Resume is a named product choice, not an implied behaviour.
    resume: Literal["continue", "from_best"] = "continue"
    resume_from: str | None = None
    subsample_frac: float = 1.0
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

        Hydra types a bare ``0`` as an int and ``0,1`` as a string, and
        rejecting the int form for a value that is about to become an
        environment variable helps nobody.
        """
        return None if value is None else str(value)

    @model_validator(mode="after")
    def validate_ranges(self):
        if not 0.0 < self.subsample_frac <= 1.0:
            raise ValueError(
                f"subsample_frac must be in (0, 1], got {self.subsample_frac}"
            )
        if self.epochs < 1:
            raise ValueError(f"epochs must be >= 1, got {self.epochs}")
        return self


class LightGBMTrainerConfig(BaseModel):
    """Harness knobs for ``LightGBMTrainer`` (the ``eval_set`` fit path)."""

    model_config = {"extra": "ignore"}

    # None -> no early stopping; train the full n_estimators.
    early_stopping_rounds: int | None = 50
    log_period: int = 0


class TuneConfig(BaseModel):
    """Optuna search, declared per trainer rather than per run.

    Off by default: a tuned run costs ``n_trials * cv`` fits, and turning
    that on should be a visible choice in the trainer's own file.
    """

    model_config = {"extra": "ignore"}

    enabled: bool = False
    n_trials: int = 20
    # Folds for the tuning CV. The *splitter* comes from split.mode (D9),
    # never a hardcoded TimeSeriesSplit.
    cv: int = 3
    # A sklearn *scoring* string (not a metric-function name): "f1_macro",
    # "accuracy", "r2", "neg_root_mean_squared_error". None -> task default.
    metric: str | None = None
    direction: Literal["maximize", "minimize"] = "maximize"


class TrainerConfig(BaseModel):
    """One entry of the ``trainer/`` config group.

    ``kind`` picks the :class:`BaseTrainer` implementation, ``name`` picks
    the estimator/architecture inside it, ``params`` are that estimator's
    own kwargs. The per-kind sections carry harness knobs only one trainer
    reads; an unused section costs nothing and keeps ``trainer=<x>`` a
    single-file swap.
    """

    model_config = {"extra": "ignore", "protected_namespaces": ()}

    kind: Literal["sklearn", "lightgbm", "torch"] = "sklearn"
    name: str = "logreg"
    # Free-form: each family has its own knobs, and the trainer passes them
    # straight through so a typo raises in the constructor, loudly.
    params: dict = {}
    tune: TuneConfig = TuneConfig()
    torch: TorchTrainerConfig = TorchTrainerConfig()
    lightgbm: LightGBMTrainerConfig = LightGBMTrainerConfig()


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
        allowed = metric_names(self.task)
        if self.selection.metric not in allowed:
            raise ValueError(
                f"selection.metric={self.selection.metric!r} is not produced "
                f"for task={self.task!r}; choose from {list(allowed)}"
            )
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

        Hydra's grammar reads that as a Python numeric literal - underscores
        are digit separators - so it arrives as the int 20260730143000 with
        the separator already gone. Coercing it back to a string would
        silently look for the wrong run, so this fails with the fix instead.
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

    top_n: int = 20
    drill_down_columns: list[str] = []


class EvaluationConfig(RunConfig):
    """predictions + ground truth -> metrics report + error triage.

    Deliberately has no model, no feature list and no preprocessing: this
    pipeline consumes what the inference pipeline produced (D4). If it ever
    needs to *build* a sample, that is the bug the one-data-path rule
    exists to prevent.
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
        allowed = metric_names(self.task)
        if self.selection_metric not in allowed:
            raise ValueError(
                f"selection_metric={self.selection_metric!r} is not produced "
                f"for task={self.task!r}; choose from {list(allowed)}"
            )
        if self.triage.top_n < 0:
            raise ValueError(f"triage.top_n must be >= 0, got {self.triage.top_n}")
        return self


# --------------------------------------------------------------- entry helper


def metric_names(task: str) -> tuple[str, ...]:
    """Metric keys the metrics module produces for a task."""
    return CLASSIFICATION_METRICS if task == "classification" else REGRESSION_METRICS


def bootstrap(cfg, schema_cls: type[BaseModel]):
    """Validate a composed Hydra config and configure logging, once.

    The one thing every entry script does before touching a pipeline:
    coerce the OmegaConf object to a plain dict, surface sections the
    schema ignores, validate, start logging, then report which values came
    from defaults (in that order - the defaults report is useless before
    handlers exist).

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
