# Pipeline Trawl — dynamic-simu-model

> Research artifact for chimera. Mined 2026-07-30 per the trawl plan
> (docs/specs/2026-07-30-pipeline-templates-trawl-plan.md, Pass 1). Source:
> the production-weight AIAP end-to-end project (v0.2.0, Python ≥3.10, 4
> pipelines: data → training → inference → optimisation, plus a Streamlit
> app and a notebook-facing `ExperimentRunner`). Read-only evidence pass;
> all paths repo-relative.

## 1. MLflow integration — `DualMLflowLogger`

`src/mlflow_utils.py` (716 L) is the whole tracking layer. One class + three
helpers: `DualMLflowLogger`, `create_dual_logger()`, `generate_run_name()`,
`mlflow_run_context()`.

**Dual-tracker, not parent/child.** `DualMLflowLogger.__init__` takes
`primary_uri` (remote/Azure, may be `None`), `local_uri` (always used,
default `./mlruns`), `experiment_name`. `dual_run()` opens **one run in each
tracker** via `client.create_run(experiment_id=..., run_name=...)` —
deliberately `MlflowClient` with explicit `run_id`, not the fluent API,
because "`mlflow.start_run()` with multiple tracking URIs" hits global state
(docstring, `mlflow_utils.py:207-210`). There are **no nested/child runs
anywhere** in the repo: per-target separation is done by name-mangling
instead (§1.2). `mlflow.autolog()` is never called; `set_tag`/`set_tags`
never called (no MLflow run tags at all — git info is logged as *params*).

Every write funnels through `_log_to_both` → `_log_to_tracker`, which is
where the graceful-degradation policy lives:

```python
        try:
            operation(client, run_id)
        except Exception as e:
            if label == "local":
                logger.error(f"Failed to log to {label} MLflow: {e}")
            else:
                logger.warning(f"Failed to log to {label} MLflow: {e}")
```

`mlflow` itself is imported lazily in `__init__` inside `try/except
ImportError` → `self.mlflow = None` → `dual_run()` yields self and no-ops.
`docs/training_pipeline_mlflow_integration.md` (`### Failure Handling`)
states the invariant: "The pipeline never fails due to MLflow issues. Local
filesystem storage (`models/`, `outputs/`) is always written regardless of
MLflow status." Same doc: "The `mlruns/` directory exists solely for MLflow
UI visibility… It is not read by any pipeline during execution."

Two guards worth keeping: if `primary_uri == local_uri` it sets
`_skip_primary = True` to avoid double-logging; `_setup_tracker` calls
`client.restore_experiment()` when `get_experiment_by_name` returns a
tombstoned experiment (`lifecycle_stage == "deleted"`).

**Batching.** `log_params` chunks at 100 via `mlflow.entities.Param` +
`client.log_batch`; `log_metrics`/`log_metrics_batch` chunk at 1000 via
`Metric(k, v, timestamp_ms, step)`. `log_metrics_batch` takes `(key, value,
step)` tuples so per-iteration curves with differing steps can go in one
call.

Candidate for skeleton: **yes** — the dual-tracker + never-fail-the-pipeline
+ batch-API + explicit-`run_id` design is the single most portable asset
here.

### 1.1 URI / experiment configuration

Resolution order (`docs/training_pipeline_mlflow_integration.md`,
`## Tracking URI Priority`): (1) `MLFLOW_TRACKING_URI` env var, *only* if
`mlflow.use_azure_mlflow_tracking_uri: true`; (2)
`mlflow.remote_tracking_uri` from config; (3) `mlflow.local_tracking_uri` —
"**Always used** for local tracking". Local is not a fallback; remote is
additive.

The unusual bit is the *hostile* env-var handling in
`src/utils.py::get_azure_mlflow_tracking_uri`: when the flag is false it
**deletes** the variable so nothing downstream can read Azure's
auto-injected URI. Companion `sanitise_msi_environment()` deletes
`MSI_ENDPOINT`, `MSI_SECRET`, `DEFAULT_IDENTITY_CLIENT_ID`,
`IDENTITY_ENDPOINT`, `IDENTITY_HEADER` (gated on `azure.sanitise_msi`,
default true). Experiment name is passed as a constructor arg —
`mlflow.set_experiment()` is never used by the pipelines (only by
`ExperimentRunner`, §7).

Candidate for skeleton: **partial** — keep the documented 3-tier priority
and the "remove the env var so nobody reads it" trick; drop everything
Azure/MSI-specific.

### 1.2 What actually gets logged (training pipeline)

All emitted *after* the stages complete, from
`src/pipelines/training_pipeline/pipeline.py::run_full_pipeline` (lines
1257-1263): `_log_mlflow_params` → `_log_mlflow_metrics` →
`_log_mlflow_hyperparams_as_metrics` → `_log_mlflow_artifacts` →
`_register_local_mlflow_models` → `_register_azure_mlflow_models`. Each
gated by `self.valid_cfg.artifact_logging.mlflow.<flag>`.

- **Params** (`_log_mlflow_params`, 1377): `git_commit`, `git_branch`,
  `git_dirty`; `data_source_type` / `data_source_azure_asset` /
  `data_source_azure_version`; `pipeline_name`, `pipeline_version`;
  `train_size`/`val_size`/`test_size`/`split_mode`; `models_dir`,
  `results_path`; then per target `{safe}_model_type` and every
  hyperparameter flattened one level (`{safe}_{param}_{nested}`).
- **Metrics** (`_log_mlflow_metrics`, 1438): `input_samples`,
  `input_features`, `train_samples`, `val_samples`, `test_samples`;
  `{RMSE|MAE|MAPE|dir_acc}_{safe}`; `cv_{DISPLAY}_{mean|std}_{safe}`;
  `shap_n_samples_{safe}`, `shap_expected_value_{safe}`.
- **Hyperparameters logged *as metrics***
  (`_log_mlflow_hyperparams_as_metrics`, 1498) so they plot/sort in the UI:
  `alpha_{safe}`, `l1_ratio_{safe}`, `learning_rate_{safe}`,
  `num_leaves_{safe}`, `best_iteration_{safe}`, `tuning_used_{safe}` (1/0).
- **Artifacts** (`_log_mlflow_artifacts`, 1531):
  `config/training_pipeline/{config.yaml, optuna_search_ranges.yaml}`,
  `config/data_pipeline/{data_pipeline.yaml, operating_boundaries.yaml}`,
  `config/config.yaml` (global), `results/training_results.json`,
  `models/{safe}/*` (whole timestamped model dir), `shap/{safe}/*`, and
  finally `logs/<logfile>` logged last, after all other logging (1270-1272).
- **Per-iteration curves**: `MLflowCallback` in
  `classes/lightgbm_forecaster.py:48` buffers
  `(f"{dataset}_{metric}_{target}", value, iteration)` during `lgb.train()`
  and `flush()`es once per target — "avoid per-iteration HTTP round-trips".
  Note LightGBM names MAE `l1`, so metric keys are `train_l1_*`/`val_l1_*`.

The per-target namespacing everywhere depends on one four-replace function,
`modules/artifact_utils.py:324`:

```python
def get_safe_metric_name(name: str) -> str:
    return name.replace(" ", "_").replace(".", "").replace("(", "").replace(")", "")
```

Candidate for skeleton: **partial** — keep the shape (git/data-source/split
params; `{metric}_{entity}` metric convention; a name-sanitiser;
hyperparams-as-metrics; config+results+model+log artifact namespaces) but
the metric *names* are project-specific.

### 1.3 Model registry

`_register_local_mlflow_models` (1625) is gated on
`mlflow.model_registry.enabled`, dispatches per model type, and wraps each
target in `try/except Exception → logger.warning` so registration failures
never abort. The pattern is `mlflow.<flavour>.save_model(path=tmp_dir)` →
`dual_logger.log_artifacts(tmp_dir, artifact_path)` →
`register_model_locally(...)`, again to dodge fluent-API global state.
ElasticNet is bundled into a `ScaledElasticNetWrapper(models, scalers,
feature_columns, target_columns)` and saved with
`mlflow.sklearn.save_model`; LightGBM saves each booster with
`mlflow.lightgbm.save_model`. Names are
`{name_prefix}{safe_target}_{model_type}` (prefix default `dev_test_`),
artifact path `registered_models/{model_name}`, tags `{model_type, target,
timestamp}`. Signatures come from `_infer_model_signature` →
`mlflow.models.infer_signature(X_test.head(5), y_test[[target]].head(5))`,
wrapped in try/except → `None`.

`register_model_locally` itself is idempotent-by-exception:
`create_registered_model` inside `try/except MlflowException` →
`logger.debug("already exists")`, then
`create_model_version(source=f"runs:/{run_id}/{artifact_path}")`.

`_register_azure_mlflow_models` (1861) bypasses MLflow Registry entirely
and uses the Azure ML SDK because "Azure ML doesn't fully support standard
MLflow Model Registry API".

Candidate for skeleton: **partial** — keep save-to-tempdir → log_artifacts
→ register, the idempotent create, the `{prefix}{entity}_{type}` naming,
tags, and best-effort signature inference. Drop the Azure branch.

## 2. Config layering: YAML → deep-merge → pydantic → (barely) CLI

**Load order** (`src/utils.py::load_configuration`, and
`docs/configuration.md` `### How Global Config Works`): pipeline YAML is
the *base*, global `src/config.yaml` is merged *on top*. Global wins — the
inverse of the usual convention, and stated as deliberate ("single source
of truth"):

```python
    if use_global_config:
        # Load global config and merge (local as base, global overrides)
        global_config = load_global_config()
        return _deep_merge(local_config, global_config)
    return local_config
```

`_deep_merge` recurses only when both sides are dicts, so an explicit
`null` in global overrides local; "To defer to local config, omit the key
from global config entirely" (`src/config.yaml` header comment).
`load_global_config()` caches into a module global `_global_config` — one
process, one config. `use_global_config=False` is the escape hatch for
self-contained experiment configs (§7).

Then in `TrainingPipeline.__init__` (`pipeline.py:109-175`) the order is:
`load_configuration` → mutate `config["logging"]["log_prefix"] =
config["mlflow"]["run_name"]` → `configure_logger(config)` →
`get_azure_mlflow_tracking_uri()` (may inject `mlflow.remote_tracking_uri`)
→ `TrainingPipelineConfig(**self.config)` → `log_config_defaults` per
section. `self.config` (raw dict) is kept for dumping; `self.valid_cfg`
(typed) is used for logic.

**Env vars never enter the config dict.** They are a parallel channel read
only by the MLflow URI resolver and Azure clients (`.env.example`:
`AZURE_*`, `MLFLOW_TRACKING_URI`).

**CLI overrides barely exist.** `src/main.py` (28 L) has *no argparse* —
training is config-only. `src/inference.py` has exactly `--inf-horizon`;
`src/optimise.py` has `--config PATH` and `--show-pareto`;
`modules/prune_outputs.py` has `--dry-run`/`--ttl`. No click/typer, no
`[project.scripts]`, no `--set key=value`, no env-var override pattern.
`docs/configuration.md` documents the intended full chain for one setting
only: "CLI arguments (`--inf-horizon`) › Constructor arguments › Global
config › Local config › Hardcoded defaults".

Candidate for skeleton: **partial** — the two-file deep-merge + `raw dict
alongside validated model` split is worth carrying; the global-wins
direction and the near-absent CLI layer are decisions to revisit, not to
copy.

### 2.1 Pydantic schema conventions

Shared base models live in `src/schema.py` (92 L):
`FeatureEngineeringConfig`, `LoggingConfig`, `InferenceModelBehaviour`,
`MlflowModelRegistry`, `MlflowConfig`, `AzureConfig`. Pipeline schemas
subclass them to add pipeline-local fields — e.g. `configs/schema.py`:

```python
class TrainingLoggingConfig(LoggingConfig):
    log_to_file: bool = True
    log_prefix: str = "training_pipeline"

class TrainingMlflowConfig(MlflowConfig):
    experiment_name: str = "default"
    live_logging: bool = False
```

Idioms worth keeping: `model_config = {"extra": "ignore"}` on the composite
(the deep merge injects sections a given pipeline doesn't use) paired with a
`mode="before"` validator that *warns* about them; `@model_validator(
mode="after")` for cross-field rules (`SplitConfig.validate_split_ratios`
uses `math.isclose(total, 1.0, rel_tol=1e-9)`; `validate_per_target_keys`
fills missing targets with a warning but **raises** on extra ones); a
discriminated union `SearchRange = FloatSearchRange | IntSearchRange |
CategoricalSearchRange`; `model_config = {"extra": "allow"}` on
`LightGBMParams` so arbitrary LightGBM knobs pass through.
`MlflowConfig.enabled` defaults `False` in schema while `src/config.yaml`
sets `true`, with the reasoning in a comment: "This schema default ensures
MLflow is OFF unless explicitly enabled, making tests and minimal configs
predictable."

Also notable: a `TargetResults` pydantic model is used *post-hoc* —
`_build_typed_target_results()` (1363) validates the incrementally-built
results dict before MLflow logging consumes it.

Consistency is uneven across pipelines: the **data pipeline has no schema
at all**; the optimisation pipeline's is at
`optimisation_pipeline/config_schema.py` (different filename, not under
`configs/`) and **re-declares its own `LoggingConfig`/`MlflowConfig` as
bare `BaseModel`s** rather than importing the shared ones; its
`validated_config` is assigned and then never read (all downstream access
is raw `self.config.get(...)`).

Candidate for skeleton: **yes** — shared-base + per-pipeline-subclass,
`extra="ignore"` + warn-on-extra, `mode="after"` cross-field validators,
and the post-hoc typed-results model are all directly reusable.

### 2.2 Defaults transparency

`src/utils.py::log_config_defaults` uses `model_fields_set` to warn about
every value the user did *not* set, recursing into nested models and
skipping `BaseModel` leaves:

```python
    defaulted = set(type(model).model_fields) - model.model_fields_set
    if defaulted:
        leaf_defaults = {
            f: getattr(model, f)
            for f in sorted(defaulted)
            if not isinstance(getattr(model, f), BaseModel)
        }
```

Called in a loop over `model_fields` with a `hasattr(sub, "enabled") and
not sub.enabled: continue` skip, so disabled sections stay quiet. It has
its own contract test (`tests/test_log_config_defaults.py`).

Candidate for skeleton: **yes** — small, generic, and solves a real "why
did it use 42?" problem.

## 3. Logging

Entirely programmatic — no `logging.config.dictConfig`/`fileConfig`, no
logging YAML anywhere. `src/utils.py::configure_logger(config)` reads
`logging.{level, log_to_file, log_dir, log_prefix, timezone}`, then:

- attaches to the **package logger `logging.getLogger("src")`**, not the
  root logger, and calls `root_logger.handlers.clear()` first (idempotent
  re-configuration);
- format is a hardcoded constant `"%(asctime)s - %(name)s - %(levelname)s -
  %(message)s"`;
- timestamps go through a custom `TimezoneFormatter(logging.Formatter)`
  overriding `formatTime` with `datetime.fromtimestamp(record.created,
  tz=ZoneInfo(tz_name))`, default `Asia/Singapore`;
- optional file handler at `{log_dir}/{log_prefix}_{YYYYmmdd_HHMMSS}.log`;
  **returns the log path** so the caller can later log it as an MLflow
  artifact — which is exactly what training does at `pipeline.py:1270`.

Every module does `logger = logging.getLogger(__name__)` (36 of 38
`getLogger` calls in `src/`), so per-module names flow into the format.
`log_prefix` is set at runtime from `mlflow.run_name`, tying the log
filename and the MLflow run display name to one config key.

A **second, independent** logging idiom exists for the Streamlit app:
`src/app/logger.py::get_logger(name)` guards on `if not logger.handlers`,
attaches its own `StreamHandler`, and uses a *different* format
(`src/app/config.py`: `"%(asctime)s | %(name)s | %(levelname)s |
%(message)s"`).

Candidate for skeleton: **yes** — the package-logger-not-root choice,
`handlers.clear()`, tz-aware formatter, and returning the log path for
artifact upload are all worth keeping verbatim. The two-conventions split
is not.

## 4. Seed threading

There is **no global seeding at all** — no `np.random.seed`, no
`random.seed`, no `PYTHONHASHSEED` in `src/` (verified by grep; the only
`np.random.seed` calls are in `tests/`). Seeds are plain constructor
kwargs, threaded by hand:

- `data.split.random_seed: 42` → `train_val_test_split(...,
  random_seed=split.random_seed)` (`pipeline.py:252`), used only in
  `shuffle`/`temporal_shuffle` modes;
- `models.defaults.{elasticnet,lightgbm}.random_seed: 42` →
  `BaseForecaster.__init__(random_seed)` → sklearn
  `random_state=self.random_seed` / LightGBM `params["seed"] =
  random_seed`;
- `optimiser.random_seed: 1` in the optimisation config — a **different
  default** from training's 42.

The seed is persisted per model (`metadata.json →
hyperparameters.random_seed`) and restored on `load()`.

Candidate for skeleton: **partial** — persisting the seed into model
metadata is good; the absence of a single seed-everything entry point and
the 42-vs-1 split are gaps a skeleton should close.

## 5. Run artifacts: timestamps, pointers, snapshots

**One timestamp per run.** `run_full_pipeline` generates it once at the top
and threads it everywhere:

```python
        self.run_timestamp = generate_timestamp(tz=self.valid_cfg.logging.timezone)
```

`modules/artifact_utils.py::generate_timestamp(tz="Asia/Singapore")` →
`datetime.now(ZoneInfo(tz)).strftime("%Y%m%d_%H%M%S")`. Two output roots,
both `base/<timestamp>/`: `outputs/training_pipeline/<ts>/` (results) and
`models/<safe_target>/<ts>/` (per-model artifacts), with
`models/<safe_target>/shap/<ts>/` for SHAP. Confirmed on disk:
`outputs/training_pipeline/20260317_092455/{config.yaml,
training_results.json}`.

**Two pointer files at the base dir, three semantics**
(`artifact_utils.py`):

- `save_latest_pointer` / `get_latest_timestamp` → `{"timestamp": "..."}`,
  mtime-free "most recent";
- `save_best_pointer` / `get_best_model_info` → `{"timestamp": ...,
  "rmse": ...}`, monotonic-improvement only:

```python
    current_best_rmse = current_best.get("rmse", float("inf")) if current_best else None
    if (current_best_rmse is None) or (rmse < current_best_rmse):
        with open(best_file, "w") as f:
            json.dump({"timestamp": timestamp, "rmse": rmse}, f, indent=2)
        return True
```

- `resolve_artifact_path(base, timestamp=None)` → explicit timestamp if
  given, else follow `latest.json`, raising `FileNotFoundError` in both
  miss cases. This is the *only* read path; nothing globs directories.

**Config snapshot** (`_save_config_backup`, 1341) dumps `self.config` — the
raw *post-merge* dict — to `{results_dir}/{timestamp}/config.yaml`.
Verified: the on-disk snapshot contains the global `mlflow.*` and
`logging.*` sections plus the runtime-injected `logging.log_prefix`, so the
snapshot faithfully records what actually ran, not what any single file
said. Reproducibility metadata beyond the config: `_collect_run_info`
(1296) writes `run_info.{git, data_source, pipeline, split_config}` into
`training_results.json`, and `get_git_info()` shells out to `git rev-parse
--short HEAD` / `--abbrev-ref HEAD` / `git status --porcelain`, returning
`"N/A"` values inside `except (subprocess.CalledProcessError,
FileNotFoundError)`.

`save_training_results` adds `created_at` (tz-aware ISO) and `timestamp`,
writes `latest.json` at the base dir, and passes everything through
`_make_serialisable` (recursive; handles `np.ndarray` → `.tolist()`,
`np.generic` → `.item()`, else `str(obj)`).

Candidate for skeleton: **yes** — single run timestamp, `base/<ts>/` dirs,
`latest.json` + `best.json` + `resolve_artifact_path` as the sole read
path, post-merge config snapshot, git+env run_info, and
`_make_serialisable` are the highest-value carry-overs in the repo.

Caveat: these helpers live under `training_pipeline/modules/`, and
**inference and optimisation each inline-duplicate**
`datetime.now(ZoneInfo(tz)).strftime(...)` rather than importing
`generate_timestamp`. Neither writes a config snapshot or timestamped dirs;
optimisation uses an overwrite-latest CSV plus append-only
`run_metadata.jsonl` / `optimisation_results.jsonl` instead. A skeleton
must hoist these to a shared module.

## 6. Model persistence & reload contract

`classes/base_forecaster.py` (216 L) defines the ABC: `fit`, `predict`,
`save(path, timestamp=None, rmse=None, data_pipeline_config=None)`,
`load(path, timestamp=None) -> Self`, plus a concrete `evaluate()` and four
static metric functions. `save`/`load` are symmetric and the *directory*,
not a single file, is the unit.

**Files written per model version** (verified on disk,
`models/Comp_K_Concentration_Lab/20260317_092455/`):

| model type | files |
|---|---|
| ElasticNet | `model.pkl` (dict target→sklearn model, pickle), `scalers.pkl` (dict target→`StandardScaler`), `metadata.json`, `confidence_intervals.json` |
| LightGBM | `model_{sanitised_target}.txt` per booster (`booster.model_to_string()`, no pickle), `metadata.json`, `confidence_intervals.json` |

**`metadata.json` is the reload contract.** `artifact_utils.py::
save_metadata` writes a fixed 10-key envelope:

```python
    metadata = {
        "model_type": model_type, "timestamp": timestamp,
        "created_at": datetime.now(ZoneInfo(tz)).isoformat(),
        "environment": get_environment_info(),
        "feature_columns": feature_columns, "target_columns": target_columns,
        "hyperparameters": hyperparameters, "training_info": training_info,
        "files": files, "data_pipeline_config": data_pipeline_config,
    }
```

`get_environment_info()` collects `python_version`, `platform`, and
best-effort `sklearn/lightgbm/pandas/numpy` versions (each in its own
`try/except ImportError`). `files` is a type→filename map so the loader
never guesses. `data_pipeline_config` embeds the **entire**
`data_pipeline.yaml` + `operating_boundaries.yaml` (~250 lines of JSON in
the real artifact) — this is what makes inference replay training-time
preprocessing regardless of what the config files say today.

**Rebuild path** is uniform across both forecasters:
`resolve_artifact_path(base, timestamp)` → `load_metadata(dir)` → restore
`feature_columns`/`target_columns`/each hyperparameter → load the weight
files. ElasticNet unpickles `model.pkl` and optionally `scalers.pkl`;
LightGBM does `lgb.Booster(model_str=...)` from the `.txt`.

The **consumer-side** contract is stricter, in
`inference_pipeline/classes/model_loader.py`: metadata is read *first* to
decide the reconstruction path; `metadata["feature_columns"]` from the
first model becomes the canonical order and every subsequent target must
match by exact list equality or it raises `ValueError("Cannot load models
with different feature sets")`; `predict()` reorders with
`X[self.feature_columns]`. Version selection: `load_model_from_latest`
requires `latest.json` (raises if missing), while `load_model_from_best`
returns `(used_best, timestamp)` and **silently falls back to
`latest.json`** when `best.json` is absent — chosen by global config
`inference_model_behaviour.model_to_use: "best" | "latest"`. Missing
features raise; extra features warn and are ignored
(`modules/feature_validation.py`). Because `get_data_pipeline_config()`
reads from metadata, the inference pipeline **inverts the stage order** —
`load_models()` before `load_data()`.

Candidate for skeleton: **yes** — directory-as-artifact, the 10-key
`metadata.json` envelope (especially `environment`, `files`, and an
embedded upstream-config blob), symmetric `save`/`load` on an ABC, and
metadata-first reconstruction with an exact feature-order contract.

## 7. Config-driven experiments (`ExperimentRunner`)

`src/experiment_runner.py` (1491 L) is a **second, parallel** MLflow
integration for notebooks: it calls `mlflow.set_tracking_uri` /
`mlflow.set_experiment` / `mlflow.start_run` **directly**, bypassing
`DualMLflowLogger` entirely. `__init__(data_config_path,
mlflow_experiment_name, mlflow_tracking_uri="mlruns", use_mlflow=True)`
raises if `use_mlflow` and no experiment name, runs
`DataPipeline(mode="train", configure_logging=False, config_path=...)`, and
exposes method-chained feature engineering (`split_data` →
`engineer_feature` → `run_experiment` → `get_results_dataframe`). One run
per experiment call; `_log_mlflow_params` truncates the feature-name list
at 450 chars to fit MLflow's param limit and logs sample counts as
*metrics*.

The experiment configs (`src/pipelines/data_pipeline/configs/custom/*.yaml`,
4 files, ~103 L each) are **self-contained** — loaded with
`use_global_config=False`, so each one re-states the global sections under
a comment block: "These are normally merged automatically, but custom
configs must include them since global config merging is skipped."

`notebooks/feature_elimination_experiment.ipynb` shows the intended driving
pattern: a constants cell (`MLFLOW_EXPERIMENT_NAME`, `LOG_ALL_RUNS =
False`, `CONFIG_PATH`, `SPLIT_PARAMS`, `BASE_LAGS`, `N_PERTURBATIONS`,
`PERTURBATION_SEED`), then `ExperimentRunner(..., use_mlflow=LOG_ALL_RUNS)`,
then a sweep loop that suppresses noise (`logging.Filter` allowing only the
notebook logger + `redirect_stdout(StringIO())` +
`warnings.simplefilter("ignore")`), and finally **one summary MLflow run** —
`with mlflow.start_run(run_name="feature_elimination_summary")` logging
aggregate params, verdict counts as metrics, and DataFrames written to a
`tempfile.TemporaryDirectory()` and uploaded as artifacts. The notebook
also validates its assumptions against the config it loaded (`if
required_ls not in LAG_STEPS: raise ValueError(...)`).

Candidate for skeleton: **partial** — the "sweep locally, log one summary
run with CSV artifacts via tempdir" pattern and the self-contained-config
escape hatch are worth keeping. The duplicated MLflow integration is
exactly what a skeleton should collapse.

## 8. Quality gates & test patterns

`.pre-commit-config.yaml` (42 L) splits by cost: `pre-commit` stage runs
`ruff-check --fix` + `ruff-format` (from `astral-sh/ruff-pre-commit` rev
`v0.14.10`); `pre-push` stage runs `pyright` and `pytest` as `language:
system` local hooks via `conda run -n dynamic-simu-model`, both with
`pass_filenames: false, always_run: true`. A third `pipelines` hook
(`python -m src.main` as a smoke test) is **commented out** with its
rationale inline: "too heavy for pre-push (requires Azure, takes minutes,
creates side effects)". `pyproject.toml`: ruff `line-length = 90`, `select
= [E, W, F, I, N, UP, ANN]`, ignoring `N803`/`N806` "to allow ML
conventions (i.e. X_train, y_test)"; pytest `pythonpath = [".", "src"]`,
one marker `uat`. `pyrightconfig.json` excludes `tests`, `data`, `models`,
`outputs`, `mlruns`, `logs` — so tests are lint-gated but not type-checked.
**No coverage config or threshold anywhere**; no mypy.

Test fixtures show two patterns worth stealing. First, `tests/conftest.py`
derives test constants from **schema defaults** so tests never read user
config — docstring: "Tests should NOT depend on user-configurable config
files (src/config.yaml, etc.)":

```python
TEST_LOOKBACK_WINDOW: int = FeatureEngineeringConfig().lookback_window  # 100
_split_defaults = SplitConfig()
TEST_TRAIN_SIZE: float = _split_defaults.train_size  # 0.7
TEST_RANDOM_SEED: int = _split_defaults.random_seed  # 42
```

Second, the schema contract tests scope themselves explicitly
(`tests/test_training_config_schema.py` docstring): "This module tests
CUSTOM validators and application logic only. Built-in Pydantic features
(Literal types, Field constraints) are not tested here as they are already
validated by Pydantic itself." The assertions are
`pytest.raises(ValidationError, match="sum to 1.0")` / `match="low.*must
be < high"` — substring/regex against the *custom* message. One test class
per sub-model plus one for the composite plus one per cross-field
validator. MLflow is neutralised declaratively via `minimal_config`'s
`"mlflow_enabled": False` (training suite) rather than by monkeypatching;
the inference suite instead patches `load_configuration`,
`configure_logger`, and `get_azure_mlflow_tracking_uri`. `hypothesis` is
optional behind a `try/except ImportError` + `requires_hypothesis =
pytest.mark.skipif(...)` guard. Artifact tests are `tmp_path`-only, and the
load-bearing one asserts the *return value* of `save_best_pointer` (`is
False` for a worse RMSE) plus a read-back through `get_best_model_info`.

Candidate for skeleton: **yes** — the cheap/expensive hook split, the
constants-from-schema-defaults conftest, the "don't re-test pydantic"
contract-test scope, and `tmp_path` pointer round-trip tests all transfer
directly.

## 9. Doc/code divergences found (the docs lead the code in places)

Worth knowing before treating any doc as spec:

1. `docs/configuration.md` says `config_backup` saves
   `config_{timestamp}.yaml`; the code writes
   `{results_dir}/{timestamp}/config.yaml` (`_save_config_backup`, 1341).
   On-disk artifact confirms the code.
2. The MLflow doc's artifact table lists `config/` as the destination; the
   code logs to `config/training_pipeline/` and `config/data_pipeline/`
   sub-namespaces (1554, 1610).
3. `docs/unit_tests.md` lists a `pipelines` pre-push hook running the full
   training pipeline; that hook is commented out.
4. `docs/unit_tests.md` shows `pytest -m "not slow"`, but only `uat` is a
   registered marker.
5. `metadata.json` in `docs/training_pipeline.md` shows
   `training_info.best_alphas`; the real ElasticNet artifact has only
   `n_selected_features`.
6. Pyright config is duplicated in `pyproject.toml` `[tool.pyright]` and
   `pyrightconfig.json`; the latter wins, making the former dead.
7. `ruff` is pinned `v0.14.10` in pre-commit but `==0.14.0` in the dev
   extra.
8. `create_dual_logger` is called three different ways:
   `create_dual_logger(self.valid_cfg.mlflow)` (training, typed),
   `create_dual_logger(mlflow_cfg)` with an explicit `enabled` guard
   (inference), and `create_dual_logger(self.config)` — the *whole* config,
   no guard (optimisation, `pipeline.py:752`). Since `create_dual_logger`
   never checks `enabled` itself, the third form silently yields
   `experiment_name="default"` instead of `"optimisation_pipeline"`. A
   skeleton should make the enabled-check live inside the factory.

## Open questions for synthesis

1. **Merge direction.** Global-overrides-local is deliberate and documented
   three times, but it is the inverse of near-universal convention and
   makes per-experiment specialisation impossible without the
   `use_global_config=False` escape hatch. Keep it, invert it, or offer
   both with an explicit `precedence:` declaration?
2. **Where do the shared helpers live?** `generate_timestamp`,
   `save_latest_pointer`, `save_best_pointer`, `resolve_artifact_path`,
   `save_metadata`, `get_git_info`, `get_safe_metric_name` are all under
   `training_pipeline/modules/artifact_utils.py`, and the other pipelines
   duplicate rather than import. A skeleton must decide the
   shared-utilities boundary before anything else.
3. **Flat run + name-mangling vs nested runs.** One MLflow run per pipeline
   execution, per-target identity encoded in metric names (`RMSE_comp_k`)
   and artifact paths. Nested runs would give native per-target comparison
   but need the fluent API or explicit `parentRunId` tags — which conflicts
   with the `MlflowClient`-with-explicit-`run_id` design that makes dual
   logging work. Which axis wins?
4. **Should `enabled` be checked in the factory or the caller?** Three
   inconsistent call sites (§9.8) argue for moving the check into
   `create_dual_logger` and returning `None`. That changes the type
   contract to `DualMLflowLogger | None`, which `mlflow_run_context`
   already tolerates.
5. **Pickle in the model contract.** ElasticNet persists via `pickle` while
   LightGBM uses a portable native text format. `metadata.json.environment`
   records library versions but nothing *validates* them on load. Does the
   skeleton mandate a portable format (joblib + version assertion? MLflow
   flavours as the primary store)?
6. **Two model stores.** Models are written twice: to
   `models/<target>/<ts>/` (authoritative, read by inference) and to the
   MLflow registry (never read back). Is the filesystem store canonical
   with MLflow as a mirror, or should the skeleton support "registry as
   source of truth" as a mode?
7. **Seeding.** No global seed exists, defaults disagree (42 vs 1), and
   reproducibility rests on each component receiving its own kwarg. Does
   the skeleton add a single `seed_everything(seed)` plus one `run.seed`
   config key, and does it then still persist per-component seeds into
   metadata?
8. **CLI layer.** Only five flags exist, unevenly across four entry points;
   training has no argparse at all. A skeleton needs a uniform decision:
   one `--config PATH` everywhere, plus `--set section.key=value` overrides
   applied *before* pydantic validation, plus `--dry-run` — and a rule for
   whether CLI overrides land in the snapshot (they must, if the snapshot
   is to stay faithful).
9. **`best.json` is single-metric.** Improvement is defined solely as lower
   RMSE, hardcoded in `save_best_pointer(base, timestamp, rmse)`.
   Generalising to `(metric_name, direction)` is a small change with a
   migration cost for existing pointer files.
10. **Config snapshot scope.** The snapshot is the post-merge pipeline
    config only; the global config and the data-pipeline YAMLs are logged
    to MLflow but *not* copied into the local run dir. Should the local run
    dir be fully self-describing (all configs + resolved values + CLI
    overrides + env fingerprint), which would also make
    `data_pipeline_config`-in-metadata redundant?
11. **Does the skeleton own an `ExperimentRunner` analogue?** The
    notebook-facing sweep runner is a genuinely different shape (many cheap
    runs, one summary run, no persistence) and currently duplicates the
    MLflow integration. Either it becomes a first-class skeleton mode or it
    is explicitly out of scope.
