# Technical reference

The four pipelines in detail: where every file lives, what each run does
step by step, what it writes, and every config key that steers it. For
"where does my change go", see [extending.md](extending.md); for the
design rationale, see the [README](../README.md).

- [Repository structure](#repository-structure)
- [Data pipeline](#data-pipeline)
- [Training pipeline](#training-pipeline)
- [Inference pipeline](#inference-pipeline)
- [Evaluation pipeline](#evaluation-pipeline)
- [The two training protocols](#the-two-training-protocols)
- [Provenance and reproducing a run](#provenance-and-reproducing-a-run)
- [Metric system](#metric-system)

## Repository structure

```
run_data.py               entry: hydra.main -> bootstrap(DataPipelineConfig) -> DataPipeline
run_training.py           entry: hydra.main -> bootstrap(TrainingConfig) -> TrainingPipeline
run_inference.py          entry: hydra.main -> bootstrap(InferenceConfig) -> InferencePipeline
run_evaluation.py         entry: hydra.main -> bootstrap(EvaluationConfig) -> EvaluationPipeline
pyproject.toml            deps, optional extras (lightgbm/xgboost/torch/tune/explain/dev), ruff, pytest
configs/
  shared/base.yaml        seed, timezone, logging, mlflow - the only shared config file
  logging.yaml            dictConfig: console handler + level-split rotating file handlers

src/PROJECT/
  __init__.py             package root; renamed wholesale when the scaffold is adopted
  schemas.py              every pipeline's composite pydantic schema, plus bootstrap()
  core/
    config.py             LoggingConfig/MlflowConfig/SplitConfig/RunConfig, defaults reporting
    logging_setup.py      configure_logging: called once, by bootstrap, never at import
    plots.py              stateless figure helpers; each writes one PNG and returns its path
    run_artifacts.py      timestamps, run dirs, latest/best pointers, metadata, snapshots, hashes
    seeding.py            set_seed: the one seed entry point
    splits.py             split membership by stable key, fingerprints, load_split_frames
    timing.py             stage_timer: logs wall time, records time_<stage>_s
    tracking.py           init_tracking, Tracker, MetricsSidecar (metrics.jsonl)
  pipelines/
    data_pipeline/
      pipeline.py         DataPipeline.run: load -> clean -> engineer_features -> write
      classes/
        dataset_writer.py DatasetWriter: stage checkpoints, output contract, manifest
      modules/
        cleaning.py       load_raw, clean, engineer_features - stateless, never .fit()
      configs/
        data_pipeline.yaml
    training_pipeline/
      pipeline.py         TrainingPipeline.run: the orchestrator; never branches on family
      classes/
        __init__.py       TRAINERS registry, get_trainer_class, build_trainer
        base_trainer.py   BaseTrainer contract, FitFrames, cross_validate, _merged_space
        logreg_trainer.py         LogisticRegressionTrainer (pooled protocol)
        random_forest_trainer.py  RandomForestTrainer (pooled protocol)
        lightgbm_trainer.py       LightGBMTrainer (standing-val protocol)
        xgboost_trainer.py        XGBoostTrainer (standing-val protocol)
        torch_trainer.py          TorchTrainer (standing-val protocol)
      modules/
        architectures.py  MLP: layer order and init rules made explicit
        callbacks.py      epoch-boundary wiring: early stopping, NaN guard, LR schedule
        checkpointing.py  checkpoint schema, DataParallel-safe load, transfer load
        datasets.py       TabularTensorDataset, make_loaders, feature-block registry
        device.py         device selection, GPU pinning, multi-GPU wrapping
        diagnostics.py    run_diagnostics: curves, importances (+ CSV), SHAP
        history.py        booster_history: eval records -> the shared history shape
        loops.py          run_one_epoch, evaluate, predict, accuracy
        model_logging.py  log_flavor_model: save_model + log_artifacts, never fluent log_model
        preprocessing.py  build_preprocessor, transformed_feature_names
        sanity.py         overfit_single_batch
        splitting.py      resolve_feature_columns, split_frame, record_splits, make_cv_splitter
      configs/
        training.yaml
        trainer/logreg.yaml, random_forest.yaml, lightgbm.yaml, xgboost.yaml, mlp.yaml
    inference_pipeline/
      pipeline.py         InferencePipeline.run: resolve run -> validate -> predict -> write
      classes/
        model_loader.py   ModelLoader: run resolution and metadata-first reload
      modules/
        validation.py     read_input, validate_features, validate_keys
      configs/
        inference.yaml
    evaluation_pipeline/
      pipeline.py         EvaluationPipeline.run: join -> score -> triage -> report
      modules/
        diagnostics.py    write_evaluation_plots: confusion, ROC, PR, calibration, residuals
        metrics.py        METRIC_FUNCTIONS, METRIC_DIRECTIONS, compute_metrics, per_class_table
        triage.py         worst_cases, predicted_confidence, error_summary, to_markdown
      configs/
        evaluation.yaml

tests/
  conftest.py                          fixtures; constants from schema defaults, tracking off
  test_core_config_seeding_timing.py   config helpers, set_seed, stage_timer
  test_core_logging_setup.py           configure_logging, handlers, rotation
  test_core_plots.py                   every figure helper, plus figure hygiene
  test_core_run_artifacts.py           timestamps, pointers, metadata, snapshots, fingerprints
  test_core_splits.py                  key building, fingerprints, apply/load_split_frames
  test_core_tracking.py                Tracker no-op behaviour and the JSONL sidecar
  test_data_pipeline.py                cleaning, features, checkpoints, manifest
  test_evaluation_pipeline.py          report, plots, join, triage
  test_inference_pipeline.py           predictions, feature contract, run selection
  test_model_logging.py                flavor logging and signature inference
  test_schemas.py                      every cross-field validator and range shape
  test_trainers.py                     the BaseTrainer contract, parametrized over all families
  test_training_pipeline.py            run artifacts, splits, pointers, protocols, diagnostics
```

The evaluation pipeline has no `classes/` directory: it holds no stateful
object.

## Data pipeline

**Purpose.** Turn the raw table into the model-input table: stateless
cleaning, stateless feature derivation, one output file plus a manifest.
It never splits and never fits anything.

### Flow

`DataPipeline.run()` in
`src/PROJECT/pipelines/data_pipeline/pipeline.py`:

1. `core/seeding.py:set_seed(config.seed)`.
2. `core/tracking.py:init_tracking(...)` with `tags={"pipeline": "data"}`.
   No `run_dir` is passed, so this pipeline writes no `metrics.jsonl`.
3. `classes/dataset_writer.py:DatasetWriter(config)`.
4. Stage `load`: `modules/cleaning.py:load_raw(raw_path, date_col)`, then
   `DatasetWriter.checkpoint("raw", df)`.
5. Stage `clean`: `modules/cleaning.py:clean(df, cleaning, key_cols)` returns
   the frame and per-reason counts; `DatasetWriter.record_counts(counts)`,
   then `DatasetWriter.checkpoint("cleaned", df)`.
6. Stage `engineer_features`:
   `modules/cleaning.py:engineer_features(df, features, date_col)`, then
   `DatasetWriter.checkpoint("features", df)`.
7. Stage `write_processed`: `DatasetWriter.write(df)` runs
   `DatasetWriter.check_contract` (keys and target survived, keys unique),
   writes the parquet, then `DatasetWriter._write_manifest`.
8. `Tracker.log_params({raw_path, processed_path})`,
   `Tracker.log_metrics({"rows_<reason>": n})`,
   `Tracker.log_artifact(manifest)`, then the entry script's log file.
9. `Tracker.end()`.

### Inputs and outputs

| | |
|---|---|
| Reads | `raw_path` (`.csv` or `.parquet`, via `core/run_artifacts.py:read_table`) |
| Writes | `processed_path`, its manifest sidecar, and one file per named checkpoint |
| Returns | the model-input table path |

### Artifacts

| File | Contents |
|---|---|
| `<processed_path>` | the model-input table: full dataset, carrying `key_cols` and `target` |
| `<processed_path stem>.manifest.json` | the sidecar; the training run embeds its `config` as `upstream_config` |
| `<checkpoint_dir>/<stage>.parquet` | one per entry in `checkpoints`, from `raw`, `cleaned`, `features` |

Manifest keys, written by `DatasetWriter._write_manifest`:
`processed_path`, `content_hash` (16 hex chars of sha256 over the file's
bytes), `rows`, `columns`, `dtypes`, `key_cols`, `target`, `row_counts`,
`stage_checkpoints`, `config`.

`row_counts` keys come from `clean()`: `input_rows`, `output_rows`, plus
`sentinels_to_nan`, `dropped_duplicate_keys` and one
`dropped_missing_<column>` per entry in `cleaning.drop_rows_missing`, each
present only when that step ran. The same counters reach the tracker as
`rows_<key>` metrics.

Stage checkpoints are diagnostic only. Nothing downstream reads them, so
adding or dropping one changes no contract.

### Config reference

`DataPipelineConfig` in `src/PROJECT/schemas.py`, defaults shown as the
schema declares them (`configs/` may override any of them).

| Key | Type | Default | Purpose |
|---|---|---|---|
| `seed` | int | `42` | The one seed source; inherited from `RunConfig`. |
| `timezone` | str | `"Asia/Singapore"` | Inherited from `RunConfig`; unread by this pipeline. |
| `output_dir` | str | `"outputs"` | Inherited from `RunConfig`; unread by this pipeline. |
| `raw_path` | str | `"data/raw/dataset.csv"` | The input table. |
| `processed_path` | str | `"data/processed/model_input.parquet"` | The model-input table; must differ from `raw_path`. |
| `checkpoints` | list[str] | `[]` | Stage boundaries to pipe out; names must come from `raw`, `cleaned`, `features`. |
| `checkpoint_dir` | str | `"data/processed"` | Where checkpoint files land. |
| `key_cols` | list[str] | `["entity_id", "date"]` | Stable row keys; must not be empty and must survive to the output. |
| `date_col` | str \| None | `"date"` | Parsed to datetime on load; source of the calendar parts. |
| `target` | str | `"target"` | Label column; must survive to the output. |
| `cleaning.sentinel_values` | list | `[]` | Values replaced with NaN before anything else. |
| `cleaning.drop_duplicates` | bool | `true` | Drop duplicate rows, keeping the first. |
| `cleaning.dedup_subset` | list[str] \| None | `None` | Dedup columns; `None` uses `key_cols`. |
| `cleaning.drop_rows_missing` | list[str] | `[]` | Drop rows with a null in any of these, counted per column. |
| `cleaning.strip_whitespace` | bool | `true` | Strip object columns. |
| `features.date_parts` | bool | `true` | Add `<date_col>_month` and `<date_col>_dayofweek`. |
| `features.drop_columns` | list[str] | `[]` | Columns to drop; may not name a key column or the target. |
| `logging.*` | section | see [shared sections](#shared-config-sections) | |
| `mlflow.*` | section | see [shared sections](#shared-config-sections) | |

Cross-field rules enforced by `DataPipelineConfig.validate_keys_survive`:
`key_cols` must be non-empty, `features.drop_columns` may not remove a key
column or the target, `processed_path` must differ from `raw_path`, and
`checkpoints` may only name stages in `STAGE_NAMES`.

## Training pipeline

**Purpose.** Split the model-input table, build the configured trainer,
let that trainer state its own protocol, fit, score, and persist a
self-describing run directory plus the pointers that make it findable.

### Flow

`TrainingPipeline.run()` in
`src/PROJECT/pipelines/training_pipeline/pipeline.py`:

1. `core/seeding.py:set_seed(config.seed)`.
2. `core/run_artifacts.py:generate_timestamp(config.timezone)` then
   `core/run_artifacts.py:make_run_dir(config.output_dir, timestamp)`.
3. `core/tracking.py:init_tracking(..., run_dir=run_dir, tags={"pipeline":
   "training", "trainer": kind})`. The `run_dir` is what turns on
   `metrics.jsonl`.
4. Stage `load_processed`: `pandas.read_parquet(config.processed_path)`,
   then `core/run_artifacts.py:file_fingerprint(config.processed_path)`.
5. `modules/splitting.py:resolve_feature_columns(df, config)` returns the
   numeric and categorical lists, declared or inferred by dtype.
6. `classes/__init__.py:build_trainer(config.trainer, task=, seed=,
   numeric_features=, categorical_features=, cv_mode=config.split.mode)`.
7. Stage `split`: `modules/splitting.py:split_frame(df, config.split,
   config.target)`, then `modules/splitting.py:record_splits(run_dir,
   frames, config.split)` which writes `splits.json` through
   `core/splits.py:save_splits` and returns the per-split fingerprints.
8. `BaseTrainer.fit_frames(X, y)` returns a `FitFrames`: the rows the fit
   consumes, the standing referee frames or `None`, and the `fit_splits`
   record.
9. Stage `tune`, only when `trainer.tune.enabled`:
   `TrainingPipeline._tune` calls `BaseTrainer.hyperparameter_tune` over
   `fit.X_fit`/`fit.y_fit`.
10. Stage `train`: `BaseTrainer.train(fit.X_fit, fit.y_fit, fit.X_ref,
    fit.y_ref)` - one unconditional call under either protocol.
11. `BaseTrainer.selection_key(metric=, basis=, split=)` returns
    `(basis, metric_key)` before anything is scored.
12. Stage `evaluate`: `BaseTrainer.evaluate_run(X, y, fit.X_fit, fit.y_fit,
    metric=, cv=, basis=, split=)` produces every number the run publishes.
13. `TrainingPipeline._log_run` logs `BaseTrainer.get_params()` plus the run
    facts below, replays `trainer.history` step-wise, then logs the metric
    set.
14. `TrainingPipeline._log_model` calls `BaseTrainer.log_model(tracker,
    X_fit.head(5))` when tracking is live; a failure warns.
15. `TrainingPipeline._log_diagnostics` runs
    `modules/diagnostics.py:run_diagnostics(run_dir, trainer, options,
    X["val"])` inside stage `diagnostics`.
16. Stage `persist`: `BaseTrainer.save(run_dir)` returns the files map,
    `core/run_artifacts.py:record_environment(run_dir)`,
    `TrainingPipeline._save_metadata` (which reads the upstream manifest
    through `data_pipeline/classes/dataset_writer.py:load_manifest` and
    calls `core/run_artifacts.py:save_metadata`), then
    `core/run_artifacts.py:save_config_snapshot`.
17. `TrainingPipeline._update_pointers`:
    `core/run_artifacts.py:save_latest_pointer` always, then
    `core/run_artifacts.py:save_best_pointer`. A refusal to compare two
    different bases warns and leaves `best.json` alone.
18. `Tracker.log_artifacts(run_dir)`, then `Tracker.log_artifact(log_path)`
    last, then `Tracker.end()` in a `finally`.

### Inputs and outputs

| | |
|---|---|
| Reads | `processed_path` (parquet), and its manifest sidecar if present |
| Writes | `<output_dir>/<timestamp>/` plus `latest.json` and `best.json` beside it |
| Returns | the run directory |

### Run-directory artifact inventory

| File | Written by | Contents |
|---|---|---|
| `model.joblib` | `save()` of `logreg`, `random_forest`, `lightgbm`, `xgboost` | one `Pipeline(preprocess, model)`, preprocessing and model together |
| `preprocessor.joblib` | `TorchTrainer.save` | the fitted `ColumnTransformer` |
| `checkpoint_last.pt` | `TorchTrainer.save` | the final-epoch state, so `resume: continue` resumes the trajectory |
| `checkpoint_best.pt` | `TorchTrainer.save` | the best-monitored weights; present only when a best state was recorded |
| `splits.json` | `core/splits.py:save_splits` | realized membership by stable key, plus fingerprints |
| `metadata.json` | `core/run_artifacts.py:save_metadata` | the reload envelope |
| `config.yaml` | `core/run_artifacts.py:save_config_snapshot` | the post-compose, post-override config that ran |
| `environment.json` | `core/run_artifacts.py:record_environment` | interpreter version plus resolved package versions |
| `metrics.jsonl` | `core/tracking.py:MetricsSidecar` | every params and metrics call, whether or not MLflow is live |
| `plots/` | `training_pipeline/modules/diagnostics.py` | the post-fit figures below |

`plots/` contents, each step individually guarded:

| File | Source | Present for |
|---|---|---|
| `training_curves.png` | `trainer.history` via `core/plots.py:plot_training_curves` | families that record per-iteration history |
| `feature_importances.png` | `feature_importances_` or `coef_` via `core/plots.py:plot_feature_importances` | everything but `torch` |
| `feature_importances.csv` | the full ranking, largest magnitude first, columns `feature,importance` | everything but `torch` |
| `shap_beeswarm.png` | `shap.Explainer` over sampled validation rows | everything but `torch`, with the `explain` extra |
| `shap_bar.png` | the same explanation | everything but `torch`, with the `explain` extra |

`metadata.json` top-level keys: `model_type`, `timestamp`, `created_at`,
`environment` (`python`, `platform`, and `packages` naming
`environment.json` rather than repeating it), `feature_columns`,
`target_columns`, `hyperparameters` (the trainer's `spec()`),
`training_info`, `files`, `upstream_config`.

`training_info` keys: `task`, `split` (the split config dump),
`split_fingerprints`, `selection` (the selection config dump),
`selection_basis`, `selection_metric_key`, `fit_splits`, `n_fit_rows`,
`metrics`, `trainer` (the family's `training_summary()`), `git`
(`commit`, `branch`, `dirty`), `processed_path`,
`processed_fingerprint`.

`files` maps artifact kind to filename - never a path - and always carries
`splits`, `config` and `environment` alongside whatever the trainer's
`save()` returned.

`metrics.jsonl` holds one JSON object per line, each with a `ts` and a
`type`:

```json
{"ts": 1767225600.0, "type": "params",  "params": {"trainer": "logreg", "n_fit": 204}}
{"ts": 1767225601.0, "type": "metrics", "step": 0,    "metrics": {"val_logloss": 0.62}}
{"ts": 1767225602.0, "type": "metrics", "step": null, "metrics": {"cv_f1_macro": 0.81}}
```

Per-iteration records carry a `step`; the final metric set and the
`time_<stage>_s` timings do not. `core/tracking.py:load_sidecar_metrics`
reads the metric records back as a tidy frame.

Tracker params recorded by `TrainingPipeline._log_run`, beyond the
trainer's own `get_params()`: `n_<split>` per split, `split_fp_<split>`
per split, `split_mode`, `n_fit`, `selection_basis`, `processed_path`,
`processed_fp`.

Pointers written beside the run directories: `latest.json`
(`{"timestamp"}`) and `best.json` (`{"timestamp", "metric", "mode",
"value"}`).

### Config reference

`TrainingConfig` in `src/PROJECT/schemas.py`. Defaults are the schema's;
the shipped `training.yaml` overrides some of them, and selects
`trainer: random_forest` through the config group.

| Key | Type | Default | Purpose |
|---|---|---|---|
| `seed` | int | `42` | The one seed source: split, estimators, CV folds, Optuna sampler. |
| `timezone` | str | `"Asia/Singapore"` | Timezone of the run timestamp. |
| `processed_path` | str | `"data/processed/model_input.parquet"` | The model-input table; hashed as the run reads it. |
| `output_dir` | str | `"outputs/training"` | Holds `<timestamp>/` run dirs and the two pointers. |
| `task` | `"classification"` \| `"regression"` | `"classification"` | Picks the default metric set and the estimator head. |
| `target` | str | `"target"` | Label column. |
| `key_cols` | list[str] | `["entity_id", "date"]` | Row identity; inherited into `split.key_cols` when that is empty. |
| `numeric_features` | list[str] | `[]` | Declared numerics; empty means infer by dtype, with a warning. |
| `categorical_features` | list[str] | `[]` | Declared categoricals; same fallback. |

**`trainer`** (`TrainerConfig`)

| Key | Type | Default | Purpose |
|---|---|---|---|
| `trainer.kind` | `logreg` \| `random_forest` \| `lightgbm` \| `xgboost` \| `torch` | `"logreg"` | The family: names the class, the config group file, and `model_type`. |
| `trainer.params` | dict | `{}` | Passed to the family's constructor untouched, so a typo raises there. |
| `trainer.tune.enabled` | bool | `false` | Run the search before the final fit. |
| `trainer.tune.n_trials` | int | `20` | Search budget in trials. |
| `trainer.tune.cv` | int | `3` | Fold count for a CV-scored search, and for the selection CV whether or not a search ran. |
| `trainer.tune.metric` | str \| None | `None` | A project metric alias; `None` uses the task default. Validated against `task`. |
| `trainer.tune.direction` | `"maximize"` \| `"minimize"` \| None | `None` | `None` infers from the metric, so an error-like metric is not maximized. |
| `trainer.tune.space` | dict[str, `IntSpace` \| `FloatSpace` \| `ChoiceSpace` \| `false`] | `{}` | Per-parameter overrides of the family's `TUNABLE`; `false` drops a name from the search. |
| `trainer.torch.*` | `TorchTrainerConfig` | see below | Harness knobs read only by `TorchTrainer`. |
| `trainer.lightgbm.*` | `BoosterConfig` | see below | Early-stopping knobs read only by `LightGBMTrainer`. |
| `trainer.xgboost.*` | `BoosterConfig` | see below | The same two knobs, read only by `XGBoostTrainer`. |

A search-space entry is one of three shapes, each with `extra="forbid"`
so the union stays deterministic:

| Shape | Fields | Defaults | Notes |
|---|---|---|---|
| `IntSpace` | `low`, `high`, `step`, `log` | `step=1`, `log=false` | `log=true` with a `step` other than 1 is rejected. |
| `FloatSpace` | `low`, `high`, `step`, `log` | `step=None`, `log=false` | `step=None` means continuous. |
| `ChoiceSpace` | `choices` | required | Untyped list: strings, numbers and `None` mix. |

**`trainer.lightgbm` / `trainer.xgboost`** (`BoosterConfig`)

| Key | Type | Default | Purpose |
|---|---|---|---|
| `early_stopping_rounds` | int \| None | `50` | Rounds without improvement before stopping; `None` trains the full `n_estimators`. |
| `log_period` | int | `0` | Rounds between eval-log lines; `0` silences them. |

**`trainer.torch`** (`TorchTrainerConfig`)

| Key | Type | Default | Purpose |
|---|---|---|---|
| `lr` | float | `0.001` | Optimizer learning rate. |
| `weight_decay` | float | `0.0` | L2 penalty. |
| `epochs` | int (>= 1) | `30` | Maximum epochs. |
| `batch_size` | int | `32` | Loader batch size. |
| `patience` | int | `5` | Early-stopping patience, in epochs. |
| `monitor.name` | str | `"val_loss"` | Any key an epoch emits: `train_loss`, `val_loss`, `train_metric`, `val_metric`, `lr`. |
| `monitor.mode` | `"min"` \| `"max"` | `"min"` | Read by both the early stopper and the LR schedule. |
| `lr_factor` | float | `0.5` | Plateau schedule multiplier. |
| `lr_patience` | int | `2` | Epochs on a plateau before the LR drops. |
| `min_lr` | float | `1e-06` | Floor for the schedule. |
| `resume` | `"continue"` \| `"from_best"` | `"continue"` | Resume the interrupted trajectory, or rewind to the best weights. |
| `resume_from` | str \| None | `None` | A prior run directory to resume from. |
| `subsample_frac` | float (0 < x <= 1) | `1.0` | Fraction of the training split drawn per epoch, re-drawn each epoch. |
| `sanity_check` | bool | `false` | Run the overfit-one-batch check before the real fit. |
| `num_workers` | int | `0` | Loader workers. |
| `pin_memory` | bool | `false` | Pin loader memory. |
| `device` | str | `"auto"` | `auto` resolves cuda, then mps, then cpu; or name one. |
| `visible_devices` | str \| None | `None` | Written to the environment before torch imports CUDA; an int from the CLI is coerced. |
| `device_order` | str | `"PCI_BUS_ID"` | CUDA device ordering. |
| `deterministic_cudnn` | bool | `false` | Deterministic kernels; slower, and raises on ops that have none. |

**`split`** (`TrainingSplitConfig`)

| Key | Type | Default | Purpose |
|---|---|---|---|
| `split.mode` | `shuffle` \| `stratified` \| `temporal` \| `group` | `"stratified"` | Drives both the holdout split and the CV splitter. `group` raises `NotImplementedError` in `split_frame`. |
| `split.train_size` | float | `0.7` | Share of rows in train. |
| `split.val_size` | float | `0.15` | Share in val. |
| `split.test_size` | float | `0.15` | Share in test; the three must sum to 1.0. |
| `split.key_cols` | list[str] | `[]` | Keys membership is recorded by; empty inherits the top-level `key_cols`. |
| `split.boundaries` | dict[str, str] | `{}` | Temporal mode only: requires `val_start` and `test_start`. New keys from the CLI need a `+`. |
| `split.seed` | int | `42` | Split seed, separate from the run seed. |
| `split.time_col` | str \| None | `None` | Temporal mode only, and required there. |

`make_cv_splitter` maps `mode` to `StratifiedKFold` (stratified), `KFold`
(shuffle), `TimeSeriesSplit` (temporal, never shuffled), `GroupKFold`
(group).

**`selection`** (`SelectionConfig`)

| Key | Type | Default | Purpose |
|---|---|---|---|
| `selection.metric` | str | `"f1_macro"` | The metric `best.json` ranks on; validated against `task`. |
| `selection.mode` | `"min"` \| `"max"` | `"max"` | Direction of the monotonic improvement test. |
| `selection.split` | `"val"` \| `"test"` | `"val"` | Which split's score selects, under the standing-val protocol only. |
| `selection.basis` | `"auto"` \| `"cv"` | `"auto"` | `auto` lets each family's protocol decide; `cv` puts every family on the procedure-CV yardstick. |

**`diagnostics`** (`DiagnosticsConfig`)

| Key | Type | Default | Purpose |
|---|---|---|---|
| `diagnostics.enabled` | bool | `true` | Master switch for the post-fit figures. |
| `diagnostics.shap.enabled` | bool | `true` | The SHAP step alone; needs the `explain` extra, and is skipped for `torch`. |
| `diagnostics.shap.sample_size` | int (>= 1) | `200` | Validation rows sampled for the explainer, on the trainer's seed. |
| `diagnostics.shap.max_display` | int (>= 1) | `20` | Features drawn in the beeswarm and bar summaries. |

## Inference pipeline

**Purpose.** Resolve a recorded training run, rebuild whatever trainer
produced it, enforce that run's feature contract, and write one keyed
predictions file. It is the only producer of predictions.

### Flow

`InferencePipeline.run()` in
`src/PROJECT/pipelines/inference_pipeline/pipeline.py`:

1. `core/tracking.py:init_tracking(...)` with `tags={"pipeline":
   "inference"}`; no `run_dir`, so no sidecar.
2. Stage `load_model`: `classes/model_loader.py:ModelLoader.load(
   expected_features=None)`, which calls `ModelLoader.resolve_run_dir`
   (explicit `model.timestamp`, else `best.json`, else `latest.json`),
   `core/run_artifacts.py:load_metadata`,
   `core/run_artifacts.py:validate_feature_columns`, then
   `get_trainer_class(metadata["model_type"]).load(run_dir)`.
3. Stage `load_input`: `modules/validation.py:read_input(input_path)`.
4. `modules/validation.py:validate_features(df,
   metadata["feature_columns"])` - a missing feature raises, extras warn.
5. Stage `predict`: `InferencePipeline._build_output` calls
   `modules/validation.py:validate_keys`, `BaseTrainer.predict`, and, when
   `include_probabilities` is on, `BaseTrainer.predict_proba` plus
   `BaseTrainer.classes_`.
6. `InferencePipeline._write_output` writes parquet or csv by suffix.
7. `Tracker.log_params({model_type, run_timestamp, input_path,
   output_path})`, `Tracker.log_metrics({"n_predictions": n})`, then the
   log file; `Tracker.end()` in a `finally`.

### Inputs and outputs

| | |
|---|---|
| Reads | `input_path` (`.csv` or `.parquet`), and the resolved training run directory |
| Writes | `output_path` only - this pipeline has no run directory |
| Returns | the predictions file path |

### Artifacts

One file, `output_path`, with columns in this order: the subset of
`key_cols` present in the input, `prediction`, then one `proba_<label>`
column per class in `classes_` order. When the family exposes no
probabilities, a log line says so and only the hard predictions are
written. The `proba_*` columns are what the evaluation pipeline's ROC, PR
and calibration figures - and the triage table's `confidence` column -
depend on.

### Config reference

`InferenceConfig` in `src/PROJECT/schemas.py`.

| Key | Type | Default | Purpose |
|---|---|---|---|
| `model.use` | `"best"` \| `"latest"` | `"best"` | Which pointer to follow; falls back to `latest.json` with a warning when `best.json` is absent. |
| `model.timestamp` | str \| None | `None` | An explicit run, which overrides `model.use` (with a warning). Must be quoted on the CLI. |
| `model.runs_dir` | str | `"outputs/training"` | Where the run directories and pointers live. |
| `input_path` | str | `"data/processed/model_input.parquet"` | The table to score. |
| `output_path` | str | `"outputs/inference/predictions.parquet"` | Must end in `.parquet` or `.csv`. |
| `key_cols` | list[str] | `["entity_id", "date"]` | Carried into the predictions file for the downstream join. |
| `include_probabilities` | bool | `true` | Write `proba_<label>` columns when the family exposes them. |
| `seed`, `output_dir`, `timezone` | | `42`, `"outputs"`, `"Asia/Singapore"` | Inherited from `RunConfig`; unread by this pipeline. |

## Evaluation pipeline

**Purpose.** Join predictions to ground truth by key, score them with the
project's metric definitions, rank the worst rows, and write a report in
both machine and human form. It builds no sample and loads no model.

### Flow

`EvaluationPipeline.run()` in
`src/PROJECT/pipelines/evaluation_pipeline/pipeline.py`:

1. `core/run_artifacts.py:generate_timestamp` then
   `core/run_artifacts.py:make_run_dir(config.output_dir, timestamp)`.
2. `core/tracking.py:init_tracking(..., run_dir=run_dir,
   tags={"pipeline": "evaluation"})`.
3. Stage `join`: `EvaluationPipeline._join` reads both tables through
   `core/run_artifacts.py:read_table`, checks required columns, refuses a
   ground-truth table with duplicate keys, and inner-joins on `key_cols`.
   Unmatched prediction rows warn.
4. `EvaluationPipeline._check_data_identity` compares
   `core/run_artifacts.py:file_fingerprint(processed_path)` against the
   `processed_fingerprint` the `best.json` run recorded, and warns on a
   mismatch.
5. `modules/metrics.py:compute_metrics(y_true, y_pred, task=)`.
6. `EvaluationPipeline._write_plots` calls
   `modules/diagnostics.py:write_evaluation_plots` and returns
   `(relative paths, curve metrics)`; the curve metrics are merged into the
   metric set before it is logged, not after.
7. `modules/metrics.py:log_metrics(metrics, "evaluation")` and
   `Tracker.log_metrics(metrics)`.
8. `EvaluationPipeline._build_report` assembles the payload from
   `modules/triage.py:worst_cases`, `modules/triage.py:error_summary`,
   `modules/metrics.py:per_class_table` and
   `EvaluationPipeline._compare_to_best`.
9. `EvaluationPipeline._write_report` writes `report.json` and the markdown
   rendering.
10. `core/run_artifacts.py:save_config_snapshot` and
    `core/run_artifacts.py:save_latest_pointer`.
11. `Tracker.log_params({predictions_path, processed_path, n_rows})`,
    `Tracker.log_artifacts(run_dir)`, then the log file; `Tracker.end()`.

### Inputs and outputs

| | |
|---|---|
| Reads | `predictions_path`, `processed_path`, and `best.json` under `runs_dir` |
| Writes | `<output_dir>/<timestamp>/` plus `latest.json` beside it |
| Returns | the run directory |

### Run-directory artifact inventory

| File | Contents |
|---|---|
| `report.json` | the full payload, numpy types coerced |
| `report.md` | the same content as markdown tables, with relative image links |
| `config.yaml` | the post-compose config that ran |
| `metrics.jsonl` | the metric sidecar, including the stage timings |
| `plots/` | the figures below |

`report.json` keys: `timestamp`, `task`, `predictions_path`,
`processed_path`, `metrics`, `error_summary`, `triage`, plus `plots` when
any figure was written, `per_class` for classification, and `comparison`
when a `best.json` was found and the selection metric is present.

`comparison` keys: `best_run`, `best_metric`, `best_basis`, `best_value`,
`evaluation_metric`, `evaluation_value`, `delta`. `best_basis` is derived
from the metric key's prefix: `cv_` reads as "k-fold CV estimate on
train+val", `val_` as "the validation split", `test_` as "the test split".

`error_summary` keys are `n_rows`, `n_correct`, `n_wrong` for
classification, and `n_rows`, `residual_mean`, `residual_std`,
`abs_error_max` for regression.

`plots/` contents:

| File | Source | Present for |
|---|---|---|
| `confusion_matrix.png` | hard predictions | classification |
| `roc_curves.png` | `proba_*` columns; also yields `roc_auc` (+ `roc_auc_<label>` for multiclass) | classification |
| `pr_curves.png` | `proba_*` columns; also yields `pr_auc` (+ `pr_auc_<label>`) | classification |
| `calibration_curve.png` | `proba_*` columns | binary classification |
| `residuals.png` | hard predictions | regression |

Without `proba_*` columns the confusion matrix is still drawn and a log
line names the three that were skipped and why.

### Config reference

`EvaluationConfig` in `src/PROJECT/schemas.py`.

| Key | Type | Default | Purpose |
|---|---|---|---|
| `predictions_path` | str | `"outputs/inference/predictions.parquet"` | The file `run_inference.py` wrote. |
| `processed_path` | str | `"data/processed/model_input.parquet"` | The ground-truth table; rehashed and compared against the training run's record. |
| `output_dir` | str | `"outputs/evaluation"` | Holds `<timestamp>/` run dirs and `latest.json`. |
| `task` | `"classification"` \| `"regression"` | `"classification"` | Picks the metric set, the triage ranking and the figures. |
| `target` | str | `"target"` | Ground-truth column in the model-input table. |
| `prediction_col` | str | `"prediction"` | Prediction column in the predictions file. |
| `key_cols` | list[str] | `["entity_id", "date"]` | Join keys; must not be empty. |
| `triage.top_n` | int (>= 0) | `20` | Rows in the error table; `0` yields an empty table. |
| `triage.drill_down_columns` | list[str] | `[]` | Extra columns carried so a bad row reads without a second join. |
| `plots.enabled` | bool | `true` | Master switch for the prediction-based figures. |
| `compare_to_best` | bool | `true` | Contrast this report against the value `best.json` recorded. |
| `runs_dir` | str | `"outputs/training"` | Where `best.json` is read from, for the comparison and the staleness check. |
| `selection_metric` | str | `"f1_macro"` | The metric compared against `best.json`; validated against `task`. |
| `timezone` | str | `"Asia/Singapore"` | Timezone of the run timestamp. |
| `seed` | int | `42` | Inherited from `RunConfig`; unread by this pipeline. |

## Shared config sections

Both sections are defined once in `src/PROJECT/core/config.py` and
subclassed by every pipeline schema, so they cannot drift apart.

| Key | Type | Default | Purpose |
|---|---|---|---|
| `logging.level` | str | `"INFO"` | Root level for the package logger. |
| `logging.log_to_file` | bool | `true` | Write the run's log file, which is uploaded as the last artifact. |
| `logging.log_dir` | str | `"logs"` | Where that file goes. |
| `logging.log_prefix` | str | `"run"` | Filename prefix; each pipeline's config sets its own. |
| `logging.timezone` | str | `"Asia/Singapore"` | Timestamps in log records. |
| `logging.config_path` | str \| None | `None` | A `dictConfig` YAML; `None` uses the programmatic console (+ file) logger. |
| `mlflow.enabled` | bool | `false` | Schema default is off so tests and minimal configs are predictable; `configs/shared/base.yaml` turns it on. |
| `mlflow.tracking_uri` | str | `"sqlite:///mlflow.db"` | Backend store; the classic file store is not used. |
| `mlflow.experiment_name` | str | `"default"` | Created if missing, restored if previously deleted. |
| `mlflow.run_name` | str \| None | `None` | Display name; the training and evaluation pipelines fall back to the run timestamp. |

Every composite schema uses `extra="ignore"`, and
`core/config.py:warn_extra_sections` logs the top-level sections a schema
will ignore rather than failing on them. `core/config.py:log_config_defaults`
then warns about every leaf value the run did not set explicitly, so an
unexpected value can be traced back to its default.

## The two training protocols

The family declares `uses_val_in_fit` and expresses the consequences
through three methods the orchestrator calls unconditionally. `pipeline.py`
never reads the flag; the family's own methods do, and so does
`BaseTrainer.cross_validate`.

| | **pooled** (`uses_val_in_fit = False`) | **standing val** (`uses_val_in_fit = True`) |
|---|---|---|
| Families | `logreg`, `random_forest` | `lightgbm`, `xgboost`, `torch` |
| `fit_frames` returns | `X_fit` = train+val concatenated in split order, `X_ref`/`y_ref` = `None`, `fit_splits = ["train", "val"]` | `X_fit` = train, `X_ref`/`y_ref` = val, `fit_splits = ["train"]` |
| Final fit | `train(X_fit, y_fit, None, None)` | `train(X_fit, y_fit, X_ref, y_ref)`, early-stopping on the referee |
| `evaluate_run` publishes | `dev_*` (the pool, in-sample), `test_*`, `cv_<metric>`, `cv_<metric>_std` | `train_*`, `val_*`, `test_*`, plus `cv_<metric>` and `cv_<metric>_std` under `basis: cv` |
| `selection_key` returns | `("cv", "cv_<metric>")` always | `(split, "<split>_<metric>")`, or `("cv", "cv_<metric>")` under `basis: cv` |
| Tuning scores a trial on | `cross_validate` over the frames it was handed | a holdout carved off those frames, which the trial early-stops against |
| `trainer.tune.cv` is read by | the search and the selection CV | the selection CV only; the search ignores it and says so |

There is no `val_*` metric under the pooled protocol on purpose: those
rows are inside the fit, and a metric labelled "val" reads as held out.
`selection.split` applies only to the standing-val protocol; a pooled run
logs one line saying it was ignored. Test is untouched under both, and
`splits.json` records all three splits under both.

Two fractions govern the carves, both in
`training_pipeline/classes/base_trainer.py`:

| Constant | Value | Where |
|---|---|---|
| `CV_STOP_FRACTION` | `0.15` | the stopping subset a CV fold carves out of its own training rows |
| `TUNE_HOLDOUT_FRACTION` | `0.2` | the holdout a standing-val search carves once, up front |

Under `split.mode: temporal` both carves take the chronological tail, so
nothing about a fit - including its early-stopping monitor - sees rows
later than the point it is evaluated at. Otherwise the carve is a
stratified split under `stratified` mode and a plain random one under the
rest, both on the trainer's seed.

`BaseTrainer.cross_validate` reruns the family's whole training procedure
per fold: a fresh trainer through `BaseTrainer.fresh()` (the `spec()`
round trip), its own preprocessing, and its own stopping carve when the
family declares one. It returns `{metric: {"mean", "std", "values"}}` and
leaves the caller's trainer unfitted.

`selection.basis: cv` is how runs of different families become rankable in
one `output_dir`: every family then publishes `cv_<metric>` and
`best.json` holds one kind of number. Without it, `save_best_pointer`
refuses to compare a `cv_` value against a `val_` one, warns, and leaves
the pointer unchanged - the run keeps everything it already wrote, and
`latest.json` still resolves to it.

## Provenance and reproducing a run

Nothing is copied to make a run replayable. It records the identity of its
two roots and the recipes everything else derives from.

| Pinned | Where |
|---|---|
| the input table's bytes | `training_info.processed_fingerprint` (and the data pipeline's manifest `content_hash`) |
| which rows went where | `splits.json`, by stable key plus a membership fingerprint |
| the config that ran | `config.yaml`, post-compose, overrides applied |
| the code | `training_info.git` - `commit`, `branch`, `dirty` |
| the winners and the yardstick | `hyperparameters.best_params`, `training_info.selection_basis`, `training_info.selection_metric_key` |
| what it ran against | `environment.json` - interpreter plus package versions |

`environment.json` records versions by distribution name through
`importlib.metadata`, for the names listed in
`core/run_artifacts.py:RECORDED_PACKAGES`: `numpy`, `pandas`,
`scikit-learn`, `pydantic`, `hydra-core`, `mlflow`, `joblib`,
`matplotlib`, `lightgbm`, `xgboost`, `torch`, `optuna`, `shap`. Anything
not installed is omitted rather than recorded as null.

Both fingerprints are the first 16 hex characters of a sha256 digest:
`core/run_artifacts.py:file_fingerprint` over a file's bytes, and
`core/splits.py:fingerprint` over a split's sorted membership.

### Asking a past run for its frames

```python
from PROJECT.core.splits import load_split_frames

X, y = load_split_frames("outputs/training/20260801_101500")
# X["train"], X["val"], X["test"] - features in the recorded order
# y["train"], y["val"], y["test"] - the recorded target

X, y = load_split_frames(run_dir, processed_path="archive/model_input.parquet")
```

`core/splits.py:load_split_frames` reads `metadata.json` for the recorded
path, the feature order and the target, verifies the table's content hash
against `training_info.processed_fingerprint`, then applies the recorded
membership through `core/splits.py:apply_splits`. It refuses rather than
approximates:

| Condition | Result |
|---|---|
| the table is not at the recorded path | `FileNotFoundError`, naming the path the run recorded |
| its bytes changed since the run read them | `ValueError`: the data that run trained on no longer exists there |
| a recorded member is missing from the table | `ValueError` from `apply_splits`, naming the split and the count |
| the run predates the fingerprint | read on membership alone; `apply_splits` still catches lost rows |

Everything downstream of the split replays from those frames through the
run's own `config.yaml`, because each derivation is seeded: the train+val
pool a pooled family fits on, the holdout a standing-val search carves,
the CV folds. Searches included - every family seeds Optuna's sampler from
the run's `seed`
(`optuna_kwargs.setdefault("sampler", optuna.samplers.TPESampler(seed=self.seed))`),
so the same spec explores the same trajectory and lands on the same
`best_params`.

### The evaluation staleness warning

`EvaluationPipeline._check_data_identity` rehashes the ground-truth table
it is about to score against and compares it with the
`processed_fingerprint` recorded by the run `best.json` names - the same
run `run_inference.py` loads by default. A mismatch logs a warning naming
both hashes and the run timestamp, and the report is still written.
Scoring an old model against refreshed data is legitimate when deliberate
and a defect when accidental, and only the reader can tell the two apart.
The check is silent when there is no training run to ask, or when that run
predates the fingerprint.

## Metric system

`src/PROJECT/pipelines/evaluation_pipeline/modules/metrics.py` is the one
place metrics are defined. The training pipeline, the trainers' `evaluate`
methods and the evaluation report all resolve names through it, so a
validation F1 and a report F1 cannot disagree.

| Alias | Implementation | Direction (`METRIC_DIRECTIONS`) | Task |
|---|---|---|---|
| `accuracy` | `sklearn.metrics.accuracy_score` | maximize | classification |
| `f1_macro` | `f1_score(average="macro", zero_division=0)` | maximize | classification |
| `rmse` | `sqrt(mean_squared_error(...))` | minimize | regression |
| `mae` | `sklearn.metrics.mean_absolute_error` | minimize | regression |
| `r2` | `sklearn.metrics.r2_score` | maximize | regression |

Task defaults, from `CLASSIFICATION_METRICS` and `REGRESSION_METRICS`:

| Task | `default_metrics(task)` | `TUNE_DEFAULT[task]` |
|---|---|---|
| `classification` | `["accuracy", "f1_macro"]` | `("f1_macro", "maximize")` |
| `regression` | `["rmse", "mae", "r2"]` | `("rmse", "minimize")` |

`metrics.py:resolve_metric` resolves in a fixed order: a project alias
first, then any function in `sklearn.metrics` by its exact name, then a
caller-supplied callable (reported under its `__name__`). Project aliases
win so `"f1_macro"` never silently becomes something else. A name that
resolves nowhere raises, listing the aliases.

Where each table is consumed:

| Consumer | Reads | Behaviour |
|---|---|---|
| `selection.metric` | `schemas.py:check_metric` via `metric_names(task)` | rejected at config time if the task never emits it |
| `trainer.tune.metric` | `schemas.py:check_metric` | same check, and it also catches a sklearn scoring string left over from an older config |
| `trainer.tune.direction` | `base_trainer.py:resolve_tune_metric` -> `METRIC_DIRECTIONS` | `None` infers the direction; an unrecorded metric must state one explicitly |
| `BaseTrainer.evaluate(metrics=[...])` | `compute_metrics` -> `resolve_metric` | accepts aliases, sklearn names and callables |
| `BaseTrainer.cross_validate(metrics=[...])` | the same, per fold | a fold score is the same measurement `best.json` prints |
| the evaluation report | `compute_metrics(y_true, y_pred, task=)` | plus `roc_auc` and `pr_auc` contributed by the curve helpers |

`schemas.py` keeps its own `CLASSIFICATION_METRICS` and
`REGRESSION_METRICS` tuples so `check_metric` can run without importing
the metrics module; they are kept in step with the definitions above.
`roc_auc` and `pr_auc` come from `core/plots.py:plot_roc_curves` and
`core/plots.py:plot_pr_curves` rather than from `METRIC_FUNCTIONS`: they
need probabilities, not hard predictions, so they exist only in the
evaluation report and are not valid `selection.metric` values.
