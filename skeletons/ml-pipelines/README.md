# ML Pipelines scaffold

Four config-driven pipelines — **data**, **training**, **inference**,
**evaluation** — sharing one utils package, one metric definition, and one
trainer contract. Model families (`logreg`, `random_forest`, `lightgbm`,
`xgboost`, `torch`) plug in behind that contract, so swapping one is a
config flag and never a code change.

## Philosophy

Five commitments this scaffold enforces structurally:

1. **The data/training boundary is the fitted/stateless line.** The data
   pipeline cleans and derives features that depend only on a row.
   Anything that needs `.fit()` lives inside a trainer, not the data
   pipeline, so fitted state refits per fold and serializes with the
   model.
2. **One data path.** Predictions are produced exactly once, by the
   inference pipeline; evaluation only joins and scores that file. A
   second sample-building path for scoring drifts from the serving path,
   and the drift surfaces as a train/serve skew that has no single place
   to trace it back to once it appears.
3. **Runs you can find again.** One timestamp per run, threaded
   everywhere; `outputs/<pipeline>/<timestamp>/`. Runs are found only
   through the `latest.json`/`best.json` pointers, never by globbing
   directories.
4. **Splits you can reproduce.** Seed and protocol are the generator; the
   recorded membership is the record. Split membership is recorded by
   stable row key plus a sha256 fingerprint, never positional index, so a
   regenerated table cannot silently shift the splits.
5. **Tracking never fails the run.** MLflow is on by default with a
   sqlite backend. Tracking failures warn and never abort a run;
   artifacts already written are never lost to a logging error, and a
   `metrics.jsonl` sidecar is written whether or not tracking is live.

## The four pipelines

| Pipeline | Entry | In | Out |
|---|---|---|---|
| Data | `run_data.py` | `data/raw/dataset.csv` | `data/processed/model_input.parquet` + manifest (+ stage checkpoints) |
| Training | `run_training.py` | model-input table | `outputs/training/<ts>/` + `latest.json`/`best.json` |
| Inference | `run_inference.py` | a table + a recorded run | `outputs/inference/predictions.parquet` |
| Evaluation | `run_evaluation.py` | predictions + ground truth | `outputs/evaluation/<ts>/report.{json,md}` |

Each pipeline directory has the same shape:

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
  → trainer.fit_frames(X, y)
  → [optional] trainer.hyperparameter_tune(...)
  → trainer.train(...)
  → trainer.evaluate_run(...)
  → post-fit diagnostics (curves, importances, SHAP)
  → trainer.save(run_dir) + metadata + snapshot + pointers
```

There is no `if trainer.kind == ...` anywhere in `pipeline.py`, and adding
a model family never touches it.

#### Two protocols, expressed by the family — not by the orchestrator

The middle four steps run one of two protocols, and the family expresses
its own through three methods the orchestrator calls unconditionally:
`fit_frames` (how this run's data is shaped for the fit), `evaluate_run`
(what the run may claim) and `selection_key` (what `best.json` therefore
means). `pipeline.py` never reads `uses_val_in_fit` — that flag is the
family's *declaration*, which its own three methods act on and which
`cross_validate` reads to decide whether a fold carves its own stopping
subset.

| | **pooled** (`uses_val_in_fit = False`) | **standing val** (`uses_val_in_fit = True`) |
|---|---|---|
| Families | `logreg`, `random_forest` | `lightgbm`, `xgboost`, `torch` |
| Tuning scores a trial on | a procedure CV over train+val pooled | a 20% holdout carved off train, which the trial early-stops against |
| Final fit | train+val pooled, no val argument | train, early-stopping on val |
| `best.json` records | `cv_<metric>` — a k-fold estimate on the pool | `<selection.split>_<metric>` |
| Metrics published | `dev_*`, `test_*`, `cv_*` | `train_*`, `val_*`, `test_*` |

A fit with no in-fit stopping criterion never reads a validation split, so
train and val are pooled into the fit and the run selects on a k-fold CV
estimate over the pool (`trainer.tune.cv` folds, fresh pipeline per fold,
`split.mode`'s splitter); families that early-stop keep val as a standing
referee outside the fit. There is no `val_*` metric under the pooled
protocol on purpose: those rows are inside the fit, and a metric labelled
"val" reads as held out.

Test is untouched under both, `splits.json` records all three splits under
both, and `metadata.json`'s `training_info` says which protocol ran
(`selection_basis`, `fit_splits`, `n_fit_rows`). `selection.split` applies
only to the standing-val protocol; a pooled run logs one line saying it was
ignored. Everything a run scores happens inside the one `evaluate_run`
call, so the whole scoring stage is one timing key, `time_evaluate_s`.

#### Comparing families: `selection.basis: cv`

The two numbers above are deliberately not rankable against each other — a
CV estimate and one split's score are different claims, and `best.json`
refuses to compare them. `selection.basis: cv` is how you get one yardstick
instead:

```bash
python run_training.py trainer=random_forest selection.basis=cv
python run_training.py trainer=lightgbm      selection.basis=cv
python run_training.py trainer=mlp           selection.basis=cv
```

Same `output_dir`, same `split` config, same `trainer.tune.cv` fold count —
and `best.json` names the winner, without anyone reading test. Under this
basis every family's selection number is a **procedure** CV on the train+val
pool: cross-validation reruns the family's whole training procedure per
fold — a fresh trainer, its own preprocessing, its own stopping carve — so
the estimate describes the procedure the run actually ships. A family whose
fit needs a stopping referee carves one out of each fold's own training
rows (15%, and the chronological **tail** under `split.mode: temporal`, so
the stopping criterion never sees rows later than the point it is evaluated
at). Its shipped fit is unchanged, and it still publishes
`train_*`/`val_*`/`test_*`; only the number `best.json` reads moves, to
`cv_<metric>`.

The cost is `trainer.tune.cv` extra fits per run — for a torch run, k full
epoch loops, which the log reports. The caveat: a *tuned* candidate's CV
estimate used hyperparameters chosen on the same pool, so it is
optimistically biased, unevenly across families. Compare untuned
candidates, or give every candidate the same search budget and read the
ranking as indicative; nested CV is the unbiased answer (Varma & Simon
2006). Then refit the winner and report test once.

### Inference: metadata-first, trainer-agnostic

`metadata.json` records `model_type`, which is the family key. The loader
maps it to a trainer class through the registry and calls that class's
`load(run_dir)`. A LightGBM run and a torch run reload through identical
code: model-specific behavior lives behind the trainer contract, so a
branch on model family in the loader would undo that.

### Evaluation: metrics plus the evidence

Joins predictions to ground truth **by key** (the two files are written by
different runs and need not share an order), then writes:

- the metric report and, for classification, a per-class table, since a
  macro average reads differently once per-class supports are visible;
- an **error triage** table: misclassifications ranked by the confidence
  of the wrong call (a confident mistake points at a labelling problem, a
  feature bug, or a genuinely hard region), or rows ranked by `|error|`
  for regression, with `drill_down_columns` carried so a bad row can be
  read without a second join;
- a comparison against the metric `best.json` recorded at training time,
  labelled with the basis of that number (a validation split, or a k-fold
  estimate on train+val), without which the delta is not readable;
- the figures below, linked from `report.md` as relative image links.

### Reproducing a run

Nothing is copied to make this work. A run records the *identity* of its
two roots — the model-input table and split membership — and the recipes
that everything else is derived by, so its frames are re-derived on demand
rather than stored:

| Pinned | Where |
|---|---|
| the input table's bytes | `training_info.processed_fingerprint` (and the data pipeline's manifest `content_hash`) |
| which rows went where | `splits.json`, by stable key plus a membership fingerprint |
| the config that ran | `config.yaml`, post-compose, overrides applied |
| the code | `training_info.git` — commit, branch, dirty flag |
| the winners and the yardstick | `hyperparameters.best_params`, `selection_basis`, `selection_metric_key` |
| what it ran against | `environment.json` — interpreter plus package versions |

Ask a past run for its own frames:

```python
from PROJECT.core.splits import load_split_frames

X, y = load_split_frames("outputs/training/20260801_101500")   # keyed train/val/test
```

It refuses rather than approximates: if the table has moved it reports the
path the run recorded, and if its contents changed it reports that the data
that run trained on no longer exists there. Pass `processed_path=` to point
at a surviving copy.

Everything downstream of the split replays from those frames through the
run's own `config.yaml` — the train+val pool a pooled family fits on, the
20% holdout a standing-val search carves, the CV folds — because each is a
seeded derivation and the seed is in the snapshot. Searches included:
Optuna's sampler is seeded from the run's `seed`, so the same spec explores
the same trajectory and lands on the same `best_params`.

The evaluation pipeline rehashes the ground-truth table it scores against
and **warns** when it is not the one the model trained on. It warns rather
than aborting: scoring an old model against refreshed data is legitimate
when deliberate and a defect when accidental.

## Diagnostic artifacts

Every run directory carries a `plots/` subdirectory. Nothing uploads it
explicitly: both pipelines already log their whole run directory as MLflow
artifacts at the end, so **a new artifact is a file written in the right
place, never a new tracking call** — and the directory on disk and the
MLflow run always show the same thing.

Each figure lands on the side that has what it needs. Model-based
diagnostics need the estimator's internals and can only be drawn while it
is in memory; prediction-based ones need the predictions table and nothing
else, so drawing them at training time would mean scoring a sample twice.

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
same warn-and-continue pattern model logging uses, so one that cannot be
drawn costs a log line and nothing else. The switches are
`diagnostics.enabled` and `diagnostics.shap.enabled` (training) and
`plots.enabled` (evaluation).

The figures are drawn directly on sklearn and matplotlib rather than
through `mlflow.models.evaluate`, which wants fluent global run state and
a served model endpoint; the core `Tracker` drives `MlflowClient` with an
explicit `run_id` to avoid that state, and these figures must also work
with tracking off. `matplotlib` is therefore a **core** dependency; `shap`
is the optional `explain` extra, and without it that one step logs a line
and is skipped.

## The trainer contract

`training_pipeline/classes/base_trainer.py`. The base is deliberately
thin: it fixes the contract and the few services that must be identical
across families for their numbers to be comparable. Everything a trainer
does to a model — `evaluate` and `hyperparameter_tune` included — is
written in that family's own class body, so a trainer file reads top to
bottom without following a hierarchy. Near-duplication between siblings is
the accepted cost of that.

| Member | Who writes it | Why |
|---|---|---|
| `_build_model()` | subclass | A **fresh**, seeded, unfitted estimator. Called per train, per CV fold, per tuning trial; a shared object would leak fitted state between folds. |
| `TUNABLE` | subclass, always | That family's search space as declared data — parameter name → default range — sitting beside the constructor those ranges are for. `trainer.tune.space` narrows any of them per run, or drops one with `false`. Annotated without a default for the same reason `uses_val_in_fit` is. |
| `_get_param_space(trial, space)` | subclass | One trial's parameters, suggested define-by-run from the merged space, plus any value derived from a suggestion (a solver's penalty, a layer list from a width and a depth). |
| `fit_frames(X, y)` | subclass, always | The frames this family's search and final fit see, as a `FitFrames` — `X_fit` (exactly the rows of `fit_splits`, in split order), the standing referee frames or `None`, and the `fit_splits` metadata records. The orchestrator then makes one unconditional `train(X_fit, y_fit, X_ref, y_ref)` call. |
| `train(X, y, X_val, y_val)` | subclass | Validation data is in the *signature* because three of the five trainers need it during the fit. |
| `uses_val_in_fit` | subclass, always | Does this family's `train` consume val? It is the family's declaration of its protocol (above): the family's own three protocol methods act on it, `cross_validate` reads it for the fold carve, and the base annotates it without defaulting it, so a new trainer that omits it fails the contract suite rather than inheriting an unchosen protocol. |
| `predict` / `predict_proba` | subclass / optional | `predict_proba` returns None when the family has none, rather than faking probabilities. |
| `evaluate(X, y, metrics=…)` | subclass, always | Three identical lines per family (`check_fitted`, then `compute_metrics` over its own predictions) and nothing inherited. The definitions still come from one place — `evaluation_pipeline/modules/metrics.py` — so no family scores itself with its own metric, but the measurement is visible in the file whose predictions it measures. |
| `evaluate_run(X, y, X_fit, y_fit, …)` | subclass, always | Every number the run publishes, in the terms its protocol supports — the pooled families score `dev_*`/`test_*` plus the CV estimate, the standing-val families score `train_*`/`val_*`/`test_*` and add the CV estimate under `selection.basis: cv`. Takes `metric`/`cv`/`basis`/`split` as plain values; no trainer ever receives a config object or the tracker. |
| `selection_key(metric, basis, split)` | subclass, always | `(basis, metric key)` — what `best.json` means for this run. Pure and callable unfitted, because the tracker params, the metadata envelope and the pointer all name the basis before there is a model to ask. |
| `cross_validate(X, y, cv, metrics)` | **base** | A fresh **trainer** per fold running this family's real `train` — including, for a family that early-stops, a stopping subset carved out of that fold's own rows. The splitter follows the run's configured `split.mode`, never a hardcoded `TimeSeriesSplit`. |
| `hyperparameter_tune(...)` | subclass, always | Abstract on the base and abstract *only* — no shared sweeper, no hooks. Every trial is scored by the procedure the family actually ships (pooled families through `cross_validate`, standing-val families on a carved 20% holdout their trials early-stop against), in project metric aliases. Winners are folded into `params` so the next `train` actually uses them. |
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
| `torch` | `TorchTrainer` | `torch` | The DL harness (epoch loop, early stopping, `ReduceLROnPlateau`, NaN guard, checkpointing, device pinning, overfit-one-batch check) as internals in `modules/`. Its tuner is the one whose winners have two destinations: `params__*` keys change the checkpoint's shapes, `options__*` keys change what the loop does. Cross-validates like every other family — the base runs its epoch loop per fold. |

Nothing is shared between the tabular families beyond the base: each
writes its own `Pipeline(preprocess, model)` assembly, its own joblib
save/load pair and its own MLflow flavor call. Four near-identical `save`
methods are the cost of each family being readable in one file.

All four of them serialize preprocessing and model **together**, so they
cannot drift apart at serving time and the inference path cannot tell them
apart.

Adding a family: implement the class, add one entry to `TRAINERS` in
`classes/__init__.py`, add `configs/trainer/<kind>.yaml`, and add it to
`ALL_TRAINERS` in `tests/conftest.py`. Nothing else changes — and
`tests/test_trainers.py` should pass for it unmodified.

### Model logging: curated flavors, no autolog

Each trainer logs its own fitted model in its own MLflow flavor
(`mlflow.sklearn`, `mlflow.lightgbm`, `mlflow.xgboost`, `mlflow.pytorch`)
after the fit, via `save_model` + `tracker.log_artifacts` — never the
fluent `mlflow.<flavor>.log_model`, because the core `Tracker` drives
`MlflowClient` with an explicit `run_id` to avoid fluent global state.
Signature inference is best-effort: a failure warns, and artifacts already
written are never lost to a logging error.

Autolog is deliberately not offered. It records per-version parameter sets
that nobody selected, fires on every cross-validation and tuning fit rather
than on the run's model, and cannot attach this run's split fingerprints.

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
  shared/base.yaml     seed, timezone, logging, mlflow  (the only shared file)
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
  `configs/` — those files belong to the analyst, so a test that reads
  them fails as soon as a knob is tuned.
- Every test runs with `mlflow.enabled=false` set declaratively, the same
  switch production uses, so the suite is hermetic without monkeypatching.
- Google-style docstrings; comments state the reason, not the action.

## Decision tables to fill in

Three choices the scaffold deliberately leaves to the project. Record the
decision in the project's own documentation, not in a comment:

- **Split protocol.** i.i.d. tabular → stratified holdout, `StratifiedKFold`
  for CV; time series → temporal boundaries and `TimeSeriesSplit`, never
  shuffled; grouped entities → `GroupKFold`. Set `split.mode`; it drives
  both the holdout split and the CV splitter used by tuning. Under
  temporal mode folds are chronological, so nothing about a fit —
  including its early-stopping monitor — sees rows later than the point it
  is evaluated at.
- **Final-fit doctrine.** Test is never trained on, under either protocol —
  what is left to decide is what happens to *val*, and the scaffold already
  answers that per family (`uses_val_in_fit`): a family that early-stops on
  val keeps it out of the fit and selects on it; one that ignores it pools
  train+val and selects on a CV estimate. Record a project-level override
  only if you want a family to depart from that — e.g. keeping a booster's
  val split out of the final fit permanently, or pooling for a family the
  scaffold does not ship.
- **Cross-family comparison.** Whether the project ranks families on
  each one's own protocol (`selection.basis: auto`, cheap, and the two kinds
  of number are then not comparable) or on one procedure-CV yardstick
  (`selection.basis: cv`, k extra fits per run, one `best.json` for all of
  them). Record which, because it changes what `best.json` means.
