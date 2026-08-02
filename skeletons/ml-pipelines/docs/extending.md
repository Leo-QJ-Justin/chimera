# Extension cookbook

Every extension has one home. Each recipe below gives the exact file, the
steps, and the check that proves it worked. For what the existing files
already contain, see [pipelines.md](pipelines.md); for why the boundaries
sit where they do, see the [README](../README.md).

1. [A new metric](#1-a-new-metric)
2. [A new training-time plot](#2-a-new-training-time-plot)
3. [A new evaluation plot](#3-a-new-evaluation-plot)
4. [A new model family](#4-a-new-model-family)
5. [A new tunable hyperparameter](#5-a-new-tunable-hyperparameter)
6. [A new cleaning step or engineered feature](#6-a-new-cleaning-step-or-engineered-feature)
7. [A new config knob](#7-a-new-config-knob)
8. [A new run artifact](#8-a-new-run-artifact)
9. [A new pipeline](#9-a-new-pipeline)

## 1. A new metric

**Home:** `src/PROJECT/pipelines/evaluation_pipeline/modules/metrics.py`.

One entry makes a metric valid everywhere at once: `selection.metric`,
`trainer.tune.metric`, `evaluate(metrics=[...])`, `cross_validate`, and the
evaluation report.

1. Add the alias to `METRIC_FUNCTIONS`, with its arguments already decided.
   That is what the table is for - whether an F-score is macro- or
   weighted-averaged is a project decision, not one to re-make per call
   site.

   ```python
   METRIC_FUNCTIONS: dict[str, Callable] = {
       ...,
       "balanced_accuracy": balanced_accuracy_score,
   }
   ```

2. Add it to `METRIC_DIRECTIONS`. Without a direction,
   `base_trainer.py:resolve_tune_metric` raises rather than assuming
   higher is better - a search run the wrong way round still completes and
   still writes a run.

   ```python
   METRIC_DIRECTIONS: dict[str, str] = {..., "balanced_accuracy": "maximize"}
   ```

3. Decide whether it belongs in the task's default set. `default_metrics`
   reads `CLASSIFICATION_METRICS` / `REGRESSION_METRICS` in the same file,
   and those tuples are what `compute_metrics` returns when the caller
   names no metrics - so adding it there puts it in every report and in
   every trainer's `evaluate()` result.

4. To name it in a config, add it to the matching tuple in
   `src/PROJECT/schemas.py` as well. `schemas.py` keeps its own copies so
   `check_metric` can validate a config without importing the metrics
   module; `metric_names(task)` reads them, and `check_metric` is what
   rejects `selection.metric` and `trainer.tune.metric` values the run
   would never emit - at config time rather than at pointer-update time,
   after the fit.

A metric that needs probabilities rather than hard predictions does not
belong here: `METRIC_FUNCTIONS` entries are called as
`f(y_true, y_pred)`. `roc_auc` and `pr_auc` reach the report from the
curve helpers instead - see [recipe 3](#3-a-new-evaluation-plot).

**Verify:** `tests/test_schemas.py::TestTrainingConfig::test_selection_metric_must_exist_for_the_task`
and `::test_tune_metric_must_exist_for_the_task` accept the new name for
its task and still reject a bogus one; extend them with a case for it.
Adding to a task's default set also changes the exact metric sets asserted
by `tests/test_trainers.py::TestContract::test_evaluate_returns_the_project_metrics`
and `tests/test_evaluation_pipeline.py::TestReport::test_metrics_match_the_project_definitions`,
which must be updated in the same change.

## 2. A new training-time plot

**Home:** the figure in `src/PROJECT/core/plots.py`, the step in
`src/PROJECT/pipelines/training_pipeline/modules/diagnostics.py`.

Model-based figures belong to the training pipeline: they need the
estimator's internals, and those exist only while it is in memory.

1. Write the figure helper in `core/plots.py`, following the shape every
   helper there has - take arrays (or a history record list) and a
   destination path, draw, and return the path `_write` gives back.
   Nothing in that module reads config or touches the tracker, and nothing
   outside it imports `pyplot`, which keeps the `matplotlib.use("Agg")` pin
   the only backend decision in the project.

2. Add a filename constant and a private step function to
   `training_pipeline/modules/diagnostics.py`, following `_training_curves`
   and `_importances`: read trainer state, return the list of paths
   written, and return an empty list with a log line when the family cannot
   support it.

3. Call it from `run_diagnostics`, wrapped in `_attempt`:

   ```python
   written += _attempt("partial dependence", _partial_dependence, trainer, plots_dir)
   ```

   `_attempt` is what makes a diagnostic unable to fail a run: an exception
   costs one warning line and nothing else.

The file lands in `<run_dir>/plots/` and mirrors to MLflow with zero
tracking code, because `TrainingPipeline.run` uploads the whole run
directory at the end of the run - and the diagnostics stage runs before
that upload. Do not add a `tracker.log_artifact` call.

Trainer state a step may read: `trainer.history`, `trainer.estimator`,
`trainer.preprocessor`, `trainer.transformed(X)`, `trainer.feature_columns`,
`trainer.model_type`, `trainer.seed`. Use
`training_pipeline/modules/preprocessing.py:transformed_feature_names` when
labelling anything indexed by the design matrix: one-hot encoding makes
that a different list from `feature_columns`.

**Verify:** `tests/test_training_pipeline.py::TestDiagnostics` - add a case
beside `test_a_one_shot_fit_gets_importances_but_no_curves`, and note that
`test_a_failing_diagnostic_costs_the_run_nothing_else` is the guard on the
`_attempt` wrapping. The figure helper itself belongs in
`tests/test_core_plots.py`, whose `TestFigureHygiene` also asserts that no
helper leaves a figure open.

## 3. A new evaluation plot

**Home:** the figure in `src/PROJECT/core/plots.py`, the step in
`src/PROJECT/pipelines/evaluation_pipeline/modules/diagnostics.py`.

Prediction-based figures belong to the evaluation pipeline: they need the
joined predictions table and nothing else, so drawing them at training
time would mean scoring a sample twice.

1. Write the figure helper in `core/plots.py`, as in
   [recipe 2](#2-a-new-training-time-plot). A helper that also produces a
   scalar returns `(path, {name: value})` - that is how `plot_roc_curves`
   and `plot_pr_curves` contribute `roc_auc` and `pr_auc`.

2. Add a filename constant and a call in `write_evaluation_plots`, on the
   branch for the task it supports, wrapped in `_attempt` (path only) or
   `_curve_attempt` (path plus metrics):

   ```python
   written += _curve_attempt(
       "lift", plot_lift_curve, y_true, proba, plots_dir / LIFT_FILENAME,
       classes, metrics=metrics,
   )
   ```

3. If the figure needs probabilities, put it in `_probability_plots`, which
   already resolves the `proba_<label>` columns the inference pipeline
   writes when `include_probabilities` is on, derives `classes` from those
   column names, and returns early with a log line when there are none. A
   figure added outside that helper will be attempted on tables that carry
   only hard predictions.

`write_evaluation_plots` returns report-relative paths
(`plots/<name>.png`) for the files that were actually written, and
`EvaluationPipeline._render_markdown` embeds exactly that list as
`![<stem>](<path>)`. Nothing needs adding to the renderer, and a figure
that was skipped is not linked. Any scalars collected go into the report's
one metric set before it is logged, so `report.json`, `metrics.jsonl` and
MLflow agree on what the evaluation measured.

**Verify:** `tests/test_evaluation_pipeline.py::TestPlots` -
`test_classification_gets_a_confusion_matrix_and_curves` for the file,
`test_the_markdown_report_links_the_images_it_wrote` for the embedding,
and `test_without_probability_columns_only_the_matrix_is_drawn` for the
`proba_*` dependency.

## 4. A new model family

**Home:** a new class in
`src/PROJECT/pipelines/training_pipeline/classes/<kind>_trainer.py`.

The checklist below is exactly what `tests/test_trainers.py` enforces. A
family that satisfies it needs no change to `pipeline.py`, to the loader,
or to any test file other than the registrations in step 4.

1. **The class.** Subclass `BaseTrainer` and declare, in the class body:

   | Member | Why it must be in this file |
   |---|---|
   | `kind` | The family key: names the class, the config group file, and `model_type`. |
   | `uses_val_in_fit` | The protocol declaration. `BaseTrainer` annotates it without defaulting it, so an omission fails the contract suite instead of inheriting an unchosen protocol. |
   | `TUNABLE` | The declared search space, non-empty, every value an `IntSpace`, `FloatSpace` or `ChoiceSpace`. |
   | `_build_model` | A fresh, seeded, unfitted estimator - never a shared object. |
   | `_get_param_space` | One trial's parameters, derived values included. |
   | `fit_frames`, `evaluate_run`, `selection_key` | The protocol trio; see [the protocol table](pipelines.md#the-two-training-protocols). |
   | `train`, `predict`, `predict_proba`, `evaluate` | The model-shaped methods. |
   | `hyperparameter_tune` | The family's own search; there is no shared sweeper to inherit. |
   | `save`, `load`, `log_model` | Persistence and the MLflow flavor. |

   `tests/test_trainers.py::OWN_ML_METHODS` lists the eleven method names
   that are checked in `cls.__dict__` rather than by attribute lookup, so
   inheriting one from a plumbing base does not satisfy the contract.
   `scale_numeric` is optional (defaults to `True`); set it `False` for
   tree ensembles. Add `extra_spec` if the constructor takes harness
   arguments `load` must hand back.

2. **Register it.** Add one entry to `TRAINERS` in
   `training_pipeline/classes/__init__.py`, mapping the kind to
   `(module name, class name)`. The import stays lazy, so an optional
   dependency does not break `import training_pipeline` on a machine that
   never installed it.

   ```python
   TRAINERS = {..., "catboost": ("catboost_trainer", "CatBoostTrainer")}
   ```

3. **Widen the schema.** Add the kind to the `TrainerConfig.kind` literal
   in `src/PROJECT/schemas.py`, or every config naming it fails
   validation. If the family needs harness knobs, add a section to
   `TrainerConfig` (as `torch`, `lightgbm` and `xgboost` have) and a branch
   in `build_trainer` that passes only that section on - the sklearn
   families pass none.

4. **Add the config group file.** `configs/trainer/<name>.yaml`, carrying
   `# @package trainer`, a `kind:` line naming the family, its `params`,
   and its `tune` block. `trainer=<name>` must always be the way to switch
   families.

5. **Register it in the suite.** Add the family to `ALL_TRAINERS` in
   `tests/conftest.py` with a tiny spec, and to `TRAINER_EXTRAS` with the
   optional modules it needs (an empty tuple means always runnable). Both
   are keyed by `kind` exactly as the config group files are, and
   `trainer_params()` parametrizes the whole contract suite over them, so a
   new family needs no new test.

6. **Declare the extra.** If it needs a dependency the scaffold does not
   ship, add a group under `[project.optional-dependencies]` in
   `pyproject.toml` and name that group in the guarded import's error
   message, so a missing install is a one-line fix rather than a traceback
   hunt.

**Verify:** `pytest tests/test_trainers.py` passes for the new family with
the file itself unmodified. `test_the_contract_suite_covers_every_registered_family`
catches a missing `ALL_TRAINERS` entry,
`test_every_registered_kind_has_a_config_group_file` catches a missing
YAML, and `tests/test_training_pipeline.py::TestTrainerSwap::test_every_trainer_produces_the_same_artifact_shape`
runs it end to end.

## 5. A new tunable hyperparameter

**Home:** the family's own `TUNABLE` table, in its trainer file.

A family is defined by its search space as much as by its constructor,
which is why the ranges sit beside the constructor they are ranges for.

1. Add the entry, using a shape from `src/PROJECT/schemas.py`:

   ```python
   TUNABLE: ClassVar[dict[str, ParamSpace]] = {
       ...,
       "min_samples_split": IntSpace(low=2, high=20),
       "learning_rate": FloatSpace(low=0.01, high=0.3, log=True),
       "max_features": ChoiceSpace(choices=["sqrt", "log2", None]),
   }
   ```

   `IntSpace` rejects `log=true` combined with a `step` other than 1, which
   is what Optuna itself refuses. All three shapes are `extra="forbid"`, so
   a misspelled field fails at config parse time rather than being ignored.

2. Most families need nothing else: their `_get_param_space` is a
   comprehension over the merged space, so a new name is suggested
   automatically.

3. **Coupled or derived parameters** are resolved in `_get_param_space`,
   which returns the *resolved* dict - including values Optuna never
   suggested. `LogisticRegressionTrainer` samples the solver first and
   derives `penalty` from it, so no trial is spent on an illegal
   combination; `TorchTrainer` turns a sampled width and depth into a
   `hidden_sizes` list. Those values survive only because each tuner
   records the resolved dict on the trial
   (`trial.set_user_attr("resolved_params", resolved)`) and reads it back
   off the winner - `study.best_params` holds what Optuna suggested, not
   what the family resolved. A parameter whose name must not be suggested
   at all when it is absent from the merged space has to be guarded
   explicitly, as `l1_ratio` is.

4. **Per-run narrowing** needs no code. `trainer.tune.space` overrides the
   declared table through `BaseTrainer._merged_space`, with three
   behaviours: `false` drops the name from the search entirely (its
   `params` value then stands, as on an untuned run); a range is merged
   field-wise onto the declared one with `exclude_unset`, so overriding
   `low`/`high` keeps a declared `log: true` and a list of choices written
   over a numeric range fails rather than half-applying; an unrecognised
   name raises, listing what the family does tune.

   ```yaml
   tune:
     space:
       min_samples_split: {low: 4, high: 8}
       max_depth: false
   ```

**Verify:** `tests/test_trainers.py::TestConfigurableSpaces` - the pattern
is `test_an_override_narrows_only_what_it_names`,
`test_a_partial_override_keeps_the_declared_scale`,
`test_disabling_a_name_takes_it_out_of_the_search` and
`test_an_unknown_name_lists_what_the_family_tunes`. For a derived value,
follow `tests/test_trainers.py::TestPerFamilySpaces::test_logreg_space_carries_its_derived_penalty`,
which asserts the derived key reaches `best_params`.
`tests/test_trainers.py::TestContract::test_declares_its_own_search_space`
already checks that every entry is a valid range shape.

## 6. A new cleaning step or engineered feature

**Home:** `src/PROJECT/pipelines/data_pipeline/modules/cleaning.py`.

**The rule that decides this:** everything in that module is stateless. It
may look at a row, a config value or a declared dtype, but it may never
learn a statistic from the training data that inference would have to
reuse. An imputer's median, a scaler's mean, an encoder's category list -
anything that needs `.fit()` - belongs inside a trainer's preprocessing
(`training_pipeline/modules/preprocessing.py`), so the fitted state refits
per fold and serializes with the model.

1. **A cleaning step** goes in `clean()`, which returns
   `(frame, counts)`. Row drops live here rather than in a fitted
   transformer, because a transformer inside the model pipeline cannot drop
   rows or touch `y`. Record a per-reason counter for anything that removes
   or alters rows:

   ```python
   before = len(df)
   df = df[df[col].between(low, high)]
   counts[f"dropped_out_of_range_{col}"] = before - len(df)
   ```

   The counters reach the manifest as `row_counts` and the tracker as
   `rows_<reason>` metrics, which is what makes a row-count drop
   interpretable rather than merely visible.

2. **An engineered feature** goes in `engineer_features()`, which takes a
   `FeatureEngineeringConfig` and the date column and returns a copy. The
   calendar parts are the reference case: they depend only on the row.

3. **Knobs** go on `CleaningConfig` or `FeatureEngineeringConfig` in
   `src/PROJECT/schemas.py`, with the matching default in
   `configs/data_pipeline.yaml` - see [recipe 7](#7-a-new-config-knob).
   `DataPipelineConfig.validate_keys_survive` already refuses a
   `features.drop_columns` that would remove a key column or the target.

4. **To inspect the result**, name the stage in `checkpoints` and read
   `<checkpoint_dir>/<stage>.parquet`. Checkpoints are diagnostic only -
   nothing downstream reads them, so adding or dropping one changes no
   contract.

**Verify:** `tests/test_data_pipeline.py::TestClean` (including
`test_is_stateless_over_its_input`, which is the guard on the rule above)
and `::TestEngineerFeatures`. `::TestDataPipeline::test_output_carries_keys_and_target`
covers the output contract, and `::TestStageCheckpoints` the inspection
path.

## 7. A new config knob

**Home:** three places, in this order.

1. **The schema field**, in `src/PROJECT/schemas.py` (or
   `src/PROJECT/core/config.py` if it is genuinely cross-pipeline). Type
   it as narrowly as it deserves - `Literal` for a closed set, `Field(ge=1)`
   for a bound - and let pydantic express what it can. Custom validators
   are for what pydantic cannot: cross-field rules such as "a temporal
   split needs a time column and boundaries". The default in the schema is
   what tests read; `tests/conftest.py` derives its constants from schema
   defaults precisely so a tuned YAML cannot break the suite.

2. **The YAML default**, in that pipeline's `configs/<name>.yaml`, with a
   comment saying what the value decides. Those files belong to the
   analyst.

3. **The read site.** Nothing else picks it up: a key nobody reads is
   silently ignored, because every composite schema is `extra="ignore"`.
   `core/config.py:warn_extra_sections` logs the top-level sections a
   schema will ignore - it catches a section in the wrong place, not a
   misspelled leaf. `core/config.py:log_config_defaults` then warns about
   every leaf the run did not set explicitly, which is how an unexpected
   value is traced back to its default.

Overriding from the CLI uses Hydra's grammar. An existing key is assigned;
a key the config does not already have needs a `+`:

```bash
python run_training.py trainer.tune.n_trials=40
python run_training.py split.mode=temporal \
  +split.boundaries.val_start=2024-03-01 +split.boundaries.test_start=2024-04-01
python run_evaluation.py '+triage.drill_down_columns=[num_a]'
```

Quote anything Hydra's grammar would read as a numeric literal -
`model.timestamp='20260730_143000'`, where the underscore is otherwise a
digit separator. `ModelSelectionConfig.reject_unquoted_timestamp` raises
with that explanation rather than coercing the mangled value back to a
string.

Overrides are as reproducible as an edit: `config.yaml` in the run
directory is the post-compose, post-override snapshot of what actually ran.

**Verify:** add a case to `tests/test_schemas.py` beside the class for that
config - `TestTrainingConfig`, `TestEvaluationConfig`, `TestTorchTrainerConfig`
and the rest are organised per schema. Then run the pipeline once with the
override and confirm the value in `<run_dir>/config.yaml`.

## 8. A new run artifact

**Home:** anywhere in the run, as long as the file lands in `run_dir`
before the end of the run.

1. Write the file into `run_dir`. The pipelines that own a run directory
   (training and evaluation) call `Tracker.log_artifacts(run_dir)` at the
   end of the run, so the file is mirrored to MLflow with no tracking call
   of its own - and the directory on disk and the MLflow run always show
   the same thing.

2. If something downstream has to find the file by name, add it to the
   `files` map. `TrainingPipeline._save_metadata` records
   `{**trainer_files, "splits": ..., "config": ..., "environment": ...}`,
   and `BaseTrainer.read_files` is how a loader resolves a filename without
   ever globbing a directory. Filenames only, never paths: the run
   directory resolves them, and it can be moved.

3. Do not add a `tracker.log_artifact` call. Two files are uploaded
   individually, and both for a reason:

   | Exception | Why |
   |---|---|
   | the `model/` flavor directory | `training_pipeline/modules/model_logging.py:log_flavor_model` saves it into a temporary directory and uploads it with `tracker.log_artifacts(path, "model")`. It exists in the MLflow run only - never in `run_dir` - because a flavor directory is MLflow's format, not the run's. |
   | the entry script's log file | Uploaded by `Tracker.log_artifact(self.log_path)` *after* `log_artifacts(run_dir)`, because it is still being written until that point, and it lives under `logging.log_dir` rather than in the run directory. |

**Verify:** `tests/test_training_pipeline.py::TestRunArtifacts::test_run_dir_is_self_describing`,
which asserts both that the expected names are present and that every
filename in `metadata.json`'s `files` map resolves inside the run
directory.

## 9. A new pipeline

**Home:** `src/PROJECT/pipelines/<name>_pipeline/`, following the shape
every existing pipeline has.

```
pipelines/<name>_pipeline/
  __init__.py      exports the pipeline class
  pipeline.py      thin orchestrator: sequences stages, owns the run dir
  classes/         stateful objects (only if there are any)
  modules/         stateless functions
  configs/
    <name>.yaml    defaults: [shared/base, _self_]; hydra.searchpath: [file://configs]
```

1. **The config class** subclasses `RunConfig` from
   `src/PROJECT/core/config.py`, which supplies `seed`, `output_dir` and
   `timezone`, and adds `logging: ProjectLoggingConfig` and
   `mlflow: MlflowConfig` like every other pipeline schema. Put it in
   `src/PROJECT/schemas.py` beside the other three, so cross-pipeline
   sections stay one definition.

2. **The YAML** lists `shared/base` **first** and `_self_` **last**, so it
   can override any shared value with its own `log_prefix` and experiment
   name, and carries the same `hydra` block: `searchpath: [file://configs]`,
   `job.chdir: false`, and a `run.dir` under `logs/hydra/`.

3. **The orchestrator** takes `(config, log_path=None)`, opens a tracker
   through `core/tracking.py:init_tracking` (passing `run_dir` if it owns
   one, which is what turns on `metrics.jsonl`), wraps each stage in
   `core/timing.py:stage_timer`, ends the tracker in a `finally`, and
   uploads the log file last.

4. **The entry script** at the project root follows `run_*.py` exactly:

   ```python
   sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

   CONFIG_PATH = "src/PROJECT/pipelines/<name>_pipeline/configs"

   @hydra.main(version_base=None, config_path=CONFIG_PATH, config_name="<name>")
   def main(cfg: DictConfig) -> None:
       config, log_path = bootstrap(cfg, <Name>Config)
       <Name>Pipeline(config, log_path=log_path).run()
   ```

   `schemas.py:bootstrap` is the whole entry contract: it coerces the
   composed config to a plain dict, surfaces sections the schema ignores,
   validates, configures logging **once**, reports which values came from
   defaults, and hands back `(config, log_path)`. Nothing else in the
   project may configure logging.

**Verify:** `python run_<name>.py mlflow.enabled=false` completes and
writes what it claims to, then add `tests/test_<name>_pipeline.py`
following `tests/test_data_pipeline.py` - a config fixture pointed at
`tmp_path` with `mlflow.enabled=false` set declaratively, which is how the
suite stays hermetic without monkeypatching.
