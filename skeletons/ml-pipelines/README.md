# ML Pipelines scaffold

Four config-driven pipelines — **data**, **training**, **inference**,
**evaluation** — sharing one utils package, one metric definition, and one
trainer contract. Model families (`logreg`, `random_forest`, `lightgbm`,
`xgboost`, `torch`) plug in behind that contract, so swapping one is a
config flag and never a code change.

Design provenance: `docs/specs/2026-07-30-pipeline-skeletons-design.md`
(decisions D1–D13, revision R1).

## Philosophy

Five commitments, each of which cost somebody a week in the corpus this
scaffold was distilled from:

1. **The data/training boundary is the fitted/stateless line (D5).** The
   data pipeline cleans and derives features that depend only on a row.
   *If it needs `.fit()`, it is not data-pipeline code* — imputers,
   scalers and encoders live inside a trainer, where per-fold refitting is
   free and the fitted state serializes with the model.
2. **One data path (D4).** Predictions are produced exactly once, by the
   inference pipeline. Evaluation consumes that file. A second
   sample-building path for scoring drifts from the serving path, and the
   drift surfaces as train/serve skew nobody can localise.
3. **Runs you can find again (D10).** One timestamp per run, threaded
   everywhere; `outputs/<pipeline>/<timestamp>/`; `latest.json` /
   `best.json` as the *only* read path. Nothing globs a directory.
4. **Splits you can reproduce (D8).** Seed + protocol is the generator;
   the recorded membership (stable keys + a sha256 fingerprint) is the
   record. Positional indices break silently when the data is regenerated.
5. **Tracking never fails the run (D3).** MLflow is on by default with a
   sqlite backend; every tracking call is wrapped, and a `metrics.jsonl`
   sidecar is written whether or not tracking is live.

## The four pipelines

| Pipeline | Entry | In | Out |
|---|---|---|---|
| Data | `run_data.py` | `data/raw/dataset.csv` | `data/processed/model_input.parquet` + manifest (+ stage checkpoints) |
| Training | `run_training.py` | model-input table | `outputs/training/<ts>/` + `latest.json`/`best.json` |
| Inference | `run_inference.py` | a table + a recorded run | `outputs/inference/predictions.parquet` |
| Evaluation | `run_evaluation.py` | predictions + ground truth | `outputs/evaluation/<ts>/report.{json,md}` |

Each pipeline directory has the same shape (R1.4):

```
pipelines/<name>/
  pipeline.py    thin orchestrator: sequences stages, owns the run dir
  classes/       stateful objects (trainers, loaders, writers)
  modules/       stateless functions (cleaning, metrics, splits, torch loops)
  configs/       that pipeline's YAML, beside the code it configures
```

### Data: stages and checkpoints

`load → clean → engineer_features`. At each stage boundary the frame can be
piped out to `data/processed/<stage>.parquet` — name the stages worth
keeping in `checkpoints: [cleaned, features]`. Those files are diagnostic
only; nothing downstream reads them, so adding or dropping one changes no
contract. The **final** stage's output is the model-input table at
`processed_path`, and the manifest sidecar (which carries the upstream
config into training metadata) attaches to that.

It never splits. The full dataset comes out, carrying `key_cols` so the
training pipeline can record split membership by stable key.

### Training: a thin orchestrator over one trainer

```
model-input table
  → split (recorded by key + fingerprint)
  → build_trainer(cfg.trainer)
  → [optional] trainer.hyperparameter_tune(...)
  → trainer.train(train, val)
  → trainer.evaluate(each split)
  → post-fit diagnostics (curves, importances, SHAP)
  → trainer.save(run_dir) + metadata + snapshot + pointers
```

There is no `if trainer.kind == ...` anywhere in `pipeline.py`, and adding
a model family never touches it.

### Inference: metadata-first, trainer-agnostic

`metadata.json` records `model_type`, which is the family key. The loader
maps it to a trainer class through the registry and calls that class's
`load(run_dir)`. A LightGBM run and a torch run reload through identical
code — which is the whole point of the contract, and the thing that would
quietly rot if the loader ever grew a branch on model family.

### Evaluation: metrics plus the evidence

Joins predictions to ground truth **by key** (the two files are written by
different runs and need not share an order), then writes:

- the metric report and, for classification, a per-class table — a macro
  F1 of 0.62 is a different story when one class has a support of 9;
- an **error triage** table: misclassifications ranked by the confidence
  of the wrong call (a confident mistake is a labelling problem, a feature
  bug, or a genuinely hard region), or rows ranked by `|error|` for
  regression, with `drill_down_columns` carried so a bad row can be read
  without a second join;
- a comparison against the metric `best.json` recorded at training time;
- the figures below, linked from `report.md` as relative image links.

## Diagnostic artifacts

Every run directory carries a `plots/` subdirectory. Nothing uploads it
explicitly: both pipelines already log their whole run directory as MLflow
artifacts at the end, so **a new artifact is a file written in the right
place, never a new tracking call** — and the directory on disk and the
MLflow run always show the same thing.

The split is by what each figure *needs*, which is why it lands on the
side it does. Model-based diagnostics need the estimator's internals and
can only be drawn while it is in memory; prediction-based ones need the
predictions table and nothing else, so drawing them at training time would
mean scoring a sample twice (the thing the one-data-path rule prevents).

| File | Pipeline | From | Present for |
|---|---|---|---|
| `plots/training_curves.png` | training | `trainer.history` | `torch`, `lightgbm`, `xgboost` |
| `plots/feature_importances.png` + `.csv` | training | `feature_importances_` or `coef_` | everything but `torch` |
| `plots/shap_beeswarm.png`, `plots/shap_bar.png` | training | `shap.Explainer` over sampled validation rows | everything but `torch`, with the `explain` extra |
| `plots/confusion_matrix.png` | evaluation | hard predictions | classification |
| `plots/roc_curves.png`, `plots/pr_curves.png` | evaluation | `proba_*` columns | classification |
| `plots/calibration_curve.png` | evaluation | `proba_*` columns | binary classification |
| `plots/residuals.png` | evaluation | hard predictions | regression |

ROC and PR also contribute `roc_auc` / `pr_auc` to the evaluation report's
metrics (macro-averaged, with per-class values, for multiclass); the curves
themselves are one-vs-rest overlaid on a single axes. `torch` is skipped
for attributions deliberately: gradient attributions for a neural net are
a different tool (captum), not a variant of `feature_importances_`.

The `proba_*` columns come from inference with `include_probabilities:
true`. Without them the confusion matrix is still drawn and a log line
says which three were skipped and why.

Boosters reach `training_curves.png` by *capturing*, not by plotting:
LightGBM's `record_evaluation` callback and XGBoost's `evals_result()` are
flattened into the same `history` shape the torch trainer fills
(`modules/history.py`), and the orchestrator replays that into MLflow
step-wise. Trainers stay free of both tracking and plotting code.

Diagnostics never fail a run. Each figure is individually wrapped in the
same warn-and-continue pattern model logging uses: one that cannot be
drawn costs a log line and nothing else. Kill switches are
`diagnostics.enabled` and `diagnostics.shap.enabled` (training) and
`plots.enabled` (evaluation).

Why hand-rolled sklearn + matplotlib rather than `mlflow.models.evaluate`:
that API wants fluent global run state and a served model endpoint, and
the core `Tracker` drives `MlflowClient` with an explicit `run_id`
precisely to avoid fluent state — plus these figures must work with
tracking off entirely. `matplotlib` is therefore a **core** dependency;
`shap` is the optional `explain` extra, and without it that one step logs
a line and is skipped.

## The trainer contract

`training_pipeline/classes/base_trainer.py`. Subclasses implement two
hooks and two methods; the base gives them three services for free.

| Member | Who writes it | Why |
|---|---|---|
| `_build_model()` | subclass | A **fresh**, seeded, unfitted estimator. Called per train, per CV fold, per tuning trial — a shared object is what makes cross-validation dishonest. |
| `_get_param_space(trial)` | subclass | That family's own Optuna space, in the estimator's own parameter names. |
| `train(X, y, X_val, y_val)` | subclass | Validation data is in the *signature* because three of the five trainers need it during the fit. |
| `predict` / `predict_proba` | subclass / optional | `predict_proba` returns None when the family has none, rather than faking probabilities. |
| `evaluate(X, y, metrics=…)` | **base** | So no family scores itself with its own metric definition. |
| `cross_validate(X, y, cv, metrics)` | **base** | Fresh model per fold; the splitter comes from `split.mode` (D9), never a hardcoded `TimeSeriesSplit`. |
| `hyperparameter_tune(...)` | **base** | Optuna over `_get_param_space`; winners are folded into `params` so the next `train` actually uses them. |
| `log_model(tracker, example)` | subclass | The fitted model in that family's own MLflow flavor. See below. |
| `save(run_dir) → files map` | subclass | Returns `{kind: filename}` verbatim for `metadata.json`. Filenames, never paths. |
| `load(run_dir)` | subclass | **Metadata-first**: read `metadata.json`, check the recorded `model_class`, rebuild from the spec, then load weights. Config files are never consulted — they may have moved on. |
| `spec()` / `get_params()` | base | `spec` is the config round-trip (what `load` reads back); `get_params` is the flat, loggable view. Separate on purpose. |

### One class per family

`trainer.kind` **is** the family: the same string names the trainer class,
its config group file, and `model_type` in the saved metadata. There is no
generic "sklearn trainer" with an estimator name inside it — a family is
defined by its search space as much as by its constructor, and a shared
lookup table has nowhere to put that.

| `kind` | Class | Extra | Notes |
|---|---|---|---|
| `logreg` | `LogisticRegressionTrainer` | — | Coupled space: the solver is sampled first and the penalty derived from it, so no trial is spent on an illegal combination. |
| `random_forest` | `RandomForestTrainer` | — | Classifier or regressor from the run's `task`. The shipped default. |
| `lightgbm` | `LightGBMTrainer` | `lightgbm` | Its own fit path: `eval_set` early stopping needs the *transformed* validation matrix, which a `Pipeline`'s fit signature cannot carry. |
| `xgboost` | `XGBoostTrainer` | `xgboost` | Same reason, different wiring — `early_stopping_rounds` is a constructor argument and raises without an `eval_set`, so it is attached only when there is a validation split. |
| `torch` | `TorchTrainer` | `torch` | The DL harness (epoch loop, early stopping, `ReduceLROnPlateau`, NaN guard, checkpointing, device pinning, overfit-one-batch check) as internals in `modules/`. Overrides `cross_validate` (refuses: a torch module is not a sklearn estimator) and `hyperparameter_tune` (holdout per trial, not k-fold). |

What is shared is *plumbing*, not identity: `classes/sklearn_common.py`
holds the `Pipeline(preprocess, model)` artifact mechanics — assemble,
predict, joblib save/load — that all four tabular families reuse, plus the
plain one-shot fit that logreg and random forest share. Every family still
writes its own `_build_model` and its own space.

All of them serialize preprocessing and model **together** (D6), so the
inference path cannot tell them apart and preprocessing can never drift
from the model it was fitted beside.

Adding a family: implement the class, add one entry to `TRAINERS` in
`classes/__init__.py`, add `configs/trainer/<kind>.yaml`, and add it to
`ALL_TRAINERS` in `tests/conftest.py`. Nothing else changes — and
`tests/test_trainers.py` should pass for it unmodified.

### Model logging: curated flavors, no autolog

Each trainer logs its own fitted model in its own MLflow flavor
(`mlflow.sklearn`, `mlflow.lightgbm`, `mlflow.xgboost`, `mlflow.pytorch`)
after the fit, via `save_model` + `tracker.log_artifacts` — never the
fluent `mlflow.<flavor>.log_model`, because the core `Tracker` drives
`MlflowClient` with an explicit `run_id` precisely to avoid fluent global
state. Signature inference is best-effort; a failure warns and the run
keeps everything it already wrote.

Autolog is deliberately not offered: it dumps per-version parameter sets
nobody curated, fires on every cross-validation and tuning fit rather than
on the run's model, and cannot attach this run's split fingerprints.

Where a flavor stores a bare booster or module rather than a pipeline
(lightgbm, xgboost, torch), the logged input example is the **transformed**
design matrix, so the recorded signature describes what that artifact
actually accepts.

## Running it

```bash
uv sync --extra lightgbm --extra xgboost --extra torch --extra tune \
        --extra explain --extra dev
python run_data.py                       # -> data/processed/model_input.parquet
python run_training.py                   # -> outputs/training/<ts>/
python run_inference.py                  # -> outputs/inference/predictions.parquet
python run_evaluation.py                 # -> outputs/evaluation/<ts>/report.md
pytest                                   # optional-extra tests skip cleanly
```

Run the entry scripts **from the project root**: `hydra.job.chdir` is off
(so every relative path in the configs resolves against your launch
directory) and `hydra.searchpath: [file://configs]` resolves there too.

Hydra overrides are the intended way to vary a run — the config snapshot
in the run dir records what actually ran, so an override is as
reproducible as an edit:

```bash
python run_training.py trainer=logreg
python run_training.py trainer=mlp trainer.torch.epochs=50 trainer.torch.patience=8
python run_training.py trainer=xgboost trainer.xgboost.early_stopping_rounds=20
python run_training.py trainer=lightgbm trainer.tune.enabled=true trainer.tune.n_trials=40
# `+` because boundaries starts empty: Hydra appends new keys, overrides existing ones.
python run_training.py split.mode=temporal \
  +split.boundaries.val_start=2024-03-01 +split.boundaries.test_start=2024-04-01
python run_inference.py model.use=latest input_path=data/raw/new_batch.csv
python run_evaluation.py triage.top_n=50 '+triage.drill_down_columns=[num_a]'
python run_data.py mlflow.enabled=false   # how the test suite stays hermetic
python run_training.py diagnostics.shap.enabled=false   # skip the slow one
python run_evaluation.py plots.enabled=false
```

**Quote timestamps.** `model.timestamp=20260730_143000` is read by Hydra's
grammar as a numeric literal (underscore = digit separator) and is
rejected with that explanation; write
`model.timestamp='20260730_143000'`.

### Config layout

```
configs/
  shared/base.yaml     seed, timezone, logging, mlflow  (the ONLY shared file)
  logging.yaml         dictConfig: console + level-split rotating files
src/PROJECT/pipelines/<name>/configs/<name>.yaml
src/PROJECT/pipelines/training_pipeline/configs/trainer/*.yaml
```

Each pipeline's config lives beside the code it configures, and pulls the
one shared block in via `hydra.searchpath`. Each pipeline file lists
`shared/base` **first** and `_self_` **last**, so it can override any
shared value (its own `log_prefix`, its own experiment name).
`shared/base.yaml` carries `# @package _global_`, which merges its sections
at the config root where the pydantic schemas expect them.

## Renaming `PROJECT`

The scaffold is self-contained — `core/` ships inside it, and imports
within the package are relative (`from ...core import run_artifacts`), so
a rename touches only the directory name and the literal `PROJECT` in
files outside the package:

```bash
grep -rIl PROJECT . --exclude-dir={.git,outputs,logs,data,.venv} \
  | xargs sed -i 's/PROJECT/my_package/g'
mv src/PROJECT src/my_package
```

That covers `run_*.py`, `tests/`, `pyproject.toml` (`[project] name`, the
wheel target, the ruff `known-first-party` list), the MLflow experiment
names in the configs, and the entry scripts' `CONFIG_PATH`. Then delete
the `"src/PROJECT/**" = ["N999"]` per-file ignore in `pyproject.toml` —
it exists only because `PROJECT` is not a valid module name.

Finally: `pre-commit install && pre-commit install --hook-type pre-push`,
and adapt the env prefix in the pre-push hooks.

## Conventions

- `logger = logging.getLogger(__name__)` in every module; logging is
  configured exactly once, by `bootstrap` in the entry script. Scalars go
  through the logger; pre-formatted blocks (the classification report) go
  through `print`, because a per-line level prefix mangles an aligned
  table.
- One seed source (`seed`), threaded explicitly and persisted into run
  metadata.
- Tests derive their constants from **schema defaults**, never from
  `configs/` — those files belong to the analyst, and a test that reads
  them fails for the wrong reason the first time someone tunes a knob.
- Every test runs with `mlflow.enabled=false` set declaratively, the same
  switch production uses, so the suite is hermetic without monkeypatching.
- Google-style docstrings; comments state the reason, not the action.

## Decision tables to fill in

Two choices the scaffold deliberately leaves to the project (record the
verdict in the project's design doc, not in a comment):

- **Split protocol (D9).** i.i.d. tabular → stratified holdout, `StratifiedKFold`
  for CV; time series → temporal boundaries and `TimeSeriesSplit`, never
  shuffled; grouped entities → `GroupKFold`. Set `split.mode`; it drives
  both the holdout split and the CV splitter used by tuning.
- **Final-fit doctrine.** Refit on train+val before serving, or keep the
  untouched holdout. The scaffold ships the second (test is scored, never
  trained on); `selection.split: val` keeps `best.json` honest.
