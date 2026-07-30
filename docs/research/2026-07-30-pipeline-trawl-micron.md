# Pipeline Trawl — Micron assessment (assessment-weight variant)

> Research artifact for chimera. Mined 2026-07-30 per the trawl plan
> (docs/specs/2026-07-30-pipeline-templates-trawl-plan.md, Pass 3). Source:
> the Micron technical assessment src code (notebooks were mined separately in
> the analysis-style reports). Total src is **498 lines of Python across 5
> modules + 6 empty `__init__.py`**. No tests, no config files, no `[tool.*]`
> section in `pyproject.toml`. This defines the floor of an assessment-weight
> skeleton: what the maintainer kept when forced to move fast.

## 1. Shape of the skeleton

```
main.py                                   21 lines  — the only entry point
src/pipelines/data_pipeline/pipeline.py  273 lines  — DataPipeline (clean/fit_transform/transform)
src/pipelines/training_pipeline/
  pipeline.py                            204 lines  — TrainingPipeline orchestrator
  classes/base_classifier.py                        — BaseClassifier ABC
  classes/{logreg,lightgbm,mlp}_classifier.py       — 3 impls
  modules/{evaluation,resampling}.py                — stateless helpers
notebooks/{eda,training}.ipynb                      — where results actually live
```

Two pipelines only: `data_pipeline` (one class) and `training_pipeline`
(orchestrator + classes/ + modules/). The `classes/` vs `modules/` split is
the load-bearing convention: **`classes/` = stateful objects behind an ABC;
`modules/` = free functions with no state**. All six `__init__.py` are empty
(verified) — every import is a full deep path, e.g.
`from src.pipelines.training_pipeline.modules.evaluation import evaluate`.

Candidate for skeleton: **yes** — the `classes/` vs `modules/` distinction is
a one-line rule that survives compression, and the empty-`__init__` +
deep-path convention means no re-export maintenance burden.

## 2. The ABC contract (`classes/base_classifier.py`)

Four `@abstractmethod`: `fit(X_train, y_train, X_val=None, y_val=None) ->
"BaseClassifier"`, `predict(X) -> np.ndarray`, `predict_proba(X) ->
np.ndarray`, `tune(X_train, y_train, n_trials=50) -> "BaseClassifier"`. Two
concrete on the base: `evaluate()` (delegates to
`modules.evaluation.evaluate`) and `get_config()`. One optional hook that
raises:

```python
def get_feature_importance(self) -> pd.DataFrame:
    raise NotImplementedError(f"{type(self).__name__} does not implement get_feature_importance")
```

Base `__init__` fixes the two universal knobs and nothing else:

```python
def __init__(self, random_seed: int = 42, smote_ratio: float = DEFAULT_SMOTE_RATIO) -> None:
    self.random_seed = random_seed
    self.smote_ratio = smote_ratio
    self.feature_columns: list[str] = []
    self.is_fitted: bool = False
```

**Config round-trip.** `get_config()` returns *constructor kwargs*, so the
round-trip is `type(clf)(**clf.get_config())`. Base returns `{"random_seed",
"smote_ratio"}`; subclasses merge tuned params in. Three different
implementation strategies for the same contract:

- LightGBM (`lightgbm_classifier.py:161`): stashes Optuna output in
  `self._tuned_params` during `tune()`, then `return {"random_seed":…,
  "smote_ratio":…, **self._tuned_params}`. Works because `__init__` takes
  `**model_kwargs`.
- LogReg (`logreg_classifier.py:147`): reads back off the estimator —
  `p = self.model.get_params()` then picks `C`, `l1_ratio`, `solver`
  explicitly.
- MLP (`mlp_classifier.py:366`): enumerates all nine attributes by hand, with
  `"device": str(self.device)` so the dict stays a plain-Python payload.

Documented contract in the base docstring, and the reason it exists:

```python
"""Subclasses extend this with their tuned hyperparameters so a fresh,
unfitted instance can be created via ``type(clf)(**clf.get_config())`` —
used to run leakage-free CV on the *tuned* configuration."""
```

The consumer is the notebook, `notebooks/training.ipynb` cell 17:
`run_cv(lambda: LightGBMClassifier(**lgbm.get_config()), train_df)`. So
`get_config` **is** the assessment-weight substitute for a serialized
model/params artifact — a factory closure instead of a file.

**`tune()` explicitly does not refit** — base docstring: "Does NOT refit —
call fit() after tune() to train on full data."
`TrainingPipeline.run_full_pipeline` honours that ordering (`self.tune(...)`
then `self.train()`).

**Seed threading** is single-source: `random_seed` enters the base ctor and
is fanned out at every stochastic site — `random_state=random_seed` into the
estimator ctor, `StratifiedKFold(..., random_state=self.random_seed)`,
`optuna.samplers.TPESampler(seed=self.random_seed)`,
`SMOTE(random_state=random_seed)`, `torch.manual_seed(self.random_seed)` as
the first line of MLP `fit()`, and `train_test_split(...,
random_state=self.random_seed)` in MLP `tune()`. `TrainingPipeline` carries
its *own* `random_seed=42` for the outer split — the two are independent and
both hard-coded to 42 (`main.py:8`, `pipeline.py:39`).

Candidate for skeleton: **yes** — 4 abstract + `get_config` +
optional-raising hook is the whole ABC. The `type(clf)(**clf.get_config())`
idiom is the cheapest possible reproducibility mechanism and should be a
named rule.

## 3. Leakage as architecture

The strongest pattern in the repo, enforced by *method naming*, not by a
Pipeline object. Module docstring of `data_pipeline/pipeline.py:1-13` states
the split up front:

```python
"""Data pipeline: stateless cleaning + fit-on-train feature engineering / selection.

* :meth:`DataPipeline.clean` — stateless, row-wise cleaning ... It computes no statistics
  across rows, so it is safe to run on the full dataset *before* the train/test split.
* :meth:`DataPipeline.fit_transform` / :meth:`DataPipeline.transform` — every
  statistic that is learned from data (imputation medians, skewness detection,
  Yeo-Johnson lambdas, RobustScaler centre/scale, collinearity selection) is fit
  on the training split only and replayed on the test split.
"""
```

**Stateless pre-split** (`clean()`, lines 97-134): add binary missingness
indicators, `dropna` on the random-missing columns. Median imputation is
*deliberately deferred* out of `clean()` — the docstring says so explicitly
("because the median is a learned statistic"), leaving NaNs in the "cleaned"
frame. That's the tell that the split is drawn by leakage-safety and not by
convenience.

**Stateful fit/transform** (lines 164-247): four learned artifacts, each
stored on `self` with an underscore, each replayed in the same order in
`transform()`: `self._medians`, `self.transformer` (Yeo-Johnson),
`self.scaler` (RobustScaler), `self._selected_cols`/`self._dropped_cols`
(Spearman collinearity). Guard on replay:

```python
if not self.is_fitted:
    raise RuntimeError("Call fit_transform() on the training split first.")
```

The orchestrator wires the ordering so the split lands *between* the two
stages (`training_pipeline/pipeline.py:83-95`):

```python
logger.info("Step 1: Clean (stateless) + stratified split")
df = self.dp.clean()
train_df, test_df = train_test_split(df, test_size=self.test_size,
                                     stratify=df[self.dp.target_col], random_state=self.random_seed)
logger.info("Step 2: Fit-transform on train, transform test")
self.X_train, self.y_train = self.dp.fit_transform(train_df)
self.X_test,  self.y_test  = self.dp.transform(test_df)
```

Per-fold CV correctness is delegated to the caller: `run_cv` in
`notebooks/training.ipynb` cell 7 instantiates `fold_dp = DataPipeline()`
fresh inside each fold, then `fit_transform(train_df.iloc[tr_idx])` /
`transform(train_df.iloc[val_idx])`. **`run_cv` lives only in the notebook —
it was never promoted into `src/`.** That is a real gap: the leakage-free CV
loop is the project's headline claim and it is unpackaged.

A second, subtler leakage device: `_SKEWED_COLS` is a frozen 61-element tuple
of column names (lines 35-41) with `detect_skewed_columns()` as a
`@staticmethod` regenerator. Rationale in-code: "applied as-is so the
transformed set is identical across folds and train/test." Auto-detection is
available but opt-in via `skewed_cols=None`. So a data-dependent decision was
**frozen into a constant on purpose** to keep the column set fold-invariant.

Candidate for skeleton: **yes** — `clean()` (stateless, pre-split) /
`fit_transform()` / `transform()` + `is_fitted` guard + "learned statistics
get an underscore attribute" is the whole contract and it's teachable in five
lines. Promoting `run_cv` into `modules/` is a **partial** — worth flagging
as the one thing the maintainer left behind under time pressure.

## 4. What replaced MLflow / config schemas / run dirs

Verified absent across all `*.py`, `*.toml`, `*.md`: `mlflow`, `joblib`,
`pickle`, `yaml`, `pydantic`, `argparse`, `typer`, `click`, `save_model`,
`dump` — **zero hits**. There is no experiment tracker, no config file, no
CLI, no timestamped run directory, and **no model persistence of any kind**.
A trained model exists only inside the Python process.

What stands in for each:

| Production concern | Assessment-weight substitute | Evidence |
|---|---|---|
| Experiment tracking | notebook cell outputs + a results table in `README.md:178-184` | README "Model Evaluation" |
| Config schema | keyword args with defaults, one hard-coded module constant per EDA finding | `_INFORMATIVE_MISSING_COLS = [80, 111]`, `_RANDOM_MISSING_COLS = [40, 69, 75]`, `_SKEWED_COLS`, `TARGET_COL`, `DEFAULT_SMOTE_RATIO = 0.1`, `CLASSES = [0, 1, 2, 3, 4]` |
| CLI / run config | `main()` with literal kwargs; README lists which literals to edit | `main.py:8-17`; `README.md:35-42` "Parameters that can be modified (in `main.py`)" |
| Run dirs / artifacts | one flat `data/processed/` overwritten each run | `save_processed()` writes `X_train.csv`/`y_train.csv`/`X_test.csv`/`y_test.csv`, no timestamp |
| Model registry | `get_config()` → factory lambda | `notebooks/training.ipynb` cells 10/17/25 |

Every hard-coded constant carries a provenance comment tying it to the EDA —
the maintainer's substitute for a config schema's documentation:

```python
# Missingness is informative for these columns (EDA 1.4.1): add binary indicator before imputing
_INFORMATIVE_MISSING_COLS = [80, 111]
# Missingness is random for these columns: drop the rows
_RANDOM_MISSING_COLS = [40, 69, 75]
```

`main.py` is itself a decision record rather than a config surface — the
comments encode *rejected* alternatives:

```python
# smote_ratio=0.0 → class-weights only, the strategy selected in training.ipynb
# (partial SMOTE was tested and rejected; it hurt LightGBM in CV).
classifier = LightGBMClassifier(random_seed=42, smote_ratio=0.0)
...
# tune_first=True runs Optuna before fitting; use_cached=True skips DataPipeline re-run
pipeline.run_full_pipeline(tune_first=False, plot_pr=True)
```

Note the honest-cost note in `resampling.py:1-16` and `README.md:204-215`:
the SMOTE knob was **kept in the code after being rejected**, explicitly "so
the experiment stays reproducible." Dead-but-documented config is a
deliberate choice here, not neglect.

The one caching affordance is `use_cached=True` in `prepare_data()` — an
`.exists()` check on `X_train.csv` that short-circuits the whole data
pipeline. Cheap, and it is what a run-dir would otherwise buy you. Caveat:
caching the *splits* means `self.dp` is left unfitted, so a cached run cannot
`transform()` new data. Fine for an assessment; a real bug in production.

Candidate for skeleton: **yes for constants-with-provenance-comments and the
decision-record `main.py`**; **partial for `use_cached`** — worth keeping but
note the unfitted-`dp` trap.

## 5. Dropped vs production — and what restores cheaply

Dropped: MLflow (or any tracker), pydantic/`config.yaml`, timestamped run
dirs, model serialization, CLI arg parsing, tests (zero files matching
`*test*`), linter/formatter config (`pyproject.toml` has **only** `[project]`
— no `[tool.ruff]`, no `[dependency-groups]`), CI, and two of four pipelines
(no inference/serving pipeline, no separate evaluation pipeline).

Restorable cheaply in a skeleton:

- **Model persistence — highest value, ~10 lines.** `get_config()` already
  exists and returns a JSON-able dict for LogReg/LightGBM (MLP's
  `hidden_sizes` tuple needs `list()`). A `save(path)`/`load(path)` pair on
  `BaseClassifier` writing `{"class": type(self).__name__, "config":
  self.get_config()}` plus a joblib/`state_dict` blob is nearly free given
  the round-trip already works. Currently the *entire* trained artifact is
  discarded at process exit.
- **A 20-line `mlflow_utils` — cheap.** The metrics dict is already the right
  shape: `evaluate()` returns `{"accuracy", "f1_macro", "mean_ap", "report"}`,
  and `get_config()` returns the params dict. One
  `log_params(clf.get_config()); log_metrics(...)` call at
  `TrainingPipeline.evaluate()`'s tail wires it. The seam is already cut.
- **A single `config.yaml` — cheap but arguably a downgrade here.** Every
  constant is already module-level and named. Moving `_SKEWED_COLS` etc. into
  YAML buys overridability but loses the inline EDA provenance comments,
  which are doing real explanatory work. Recommend: keep constants in-module,
  add config only for the run knobs currently literal in `main.py`
  (`data_path`, `test_size`, `random_seed`, `n_trials`, `smote_ratio`).
- **Timestamped run dirs — cheap.** `save_processed()` already takes a
  `processed_path`; one `datetime.now().strftime` in the ctor gets you run
  isolation. Ditto `plot_pr_curves(save_path=...)`, which already supports a
  path and is invoked with `pr_save_path=None`.
- **Promote `run_cv` from notebook to `modules/` — cheap, ~15 lines**, and
  it's the headline claim.

Not cheap / correctly dropped: a serving pipeline, CI, a full test suite.

Candidate for skeleton: **partial** — the skeleton floor should include model
save/load and a metrics-logging seam (both nearly free given
`get_config()`/`evaluate()` already return dicts). MLflow itself, run dirs,
and pydantic stay out of the assessment-weight tier.

## 6. Logging vs print, and notebook-import structure

**Exactly one `print()` in all of `src/` + `main.py`** — and it is
intentional (`training_pipeline/pipeline.py:161`):

```python
logger.info(f"  Accuracy  : {self.results['accuracy']:.4f}")
logger.info(f"  F1 (macro): {self.results['f1_macro']:.4f}")
logger.info(f"  Mean AP   : {self.results['mean_ap']:.4f}")
print(self.results["report"])
```

The rule reads as: **scalars and progress → `logger.info`; pre-formatted
multi-line blocks → `print`** (sklearn's `classification_report` string would
be mangled by a `%(levelname)s |` prefix on line one only).

Conventions:
- `logger = logging.getLogger(__name__)` at module top in every file that
  logs (5 of 5).
- Logging density tracks orchestration: `training_pipeline/pipeline.py` 15
  calls, `data_pipeline/pipeline.py` 9, MLP 5, LightGBM/LogReg 2 each, and
  **zero in `evaluation.py` and `resampling.py`** — pure helper modules never
  log. Clean rule.
- **`logging.basicConfig` is called exactly once, and only inside
  `run_full_pipeline()`** (`pipeline.py:190`) — never at import time. So
  importing `src` into a notebook does not hijack root logging; the notebook
  calls its own `logging.basicConfig(level=logging.INFO, format='%(levelname)s
  | %(message)s')` (training.ipynb cell 3, identical format string).
- Two-space-indented continuation messages (`"  Cleaned: {df.shape}"`) give
  visual nesting under the un-indented step banners (`"Step 1: ..."`). Banner
  style: `logger.info("=" * 60)` around the title.
- Library noise suppressed at module import in all three classifiers:
  `optuna.logging.set_verbosity(optuna.logging.WARNING)`, plus `verbose=-1`
  on LGBM and `lgb.log_evaluation(0)`.

**Structured for notebook import.** Every stage is callable independently and
returns its data rather than mutating hidden state — `clean() -> df`,
`fit_transform(df) -> (X, y)`, `evaluate(...) -> dict`, and the plotters take
`save_path: str | None = None` where `None` means `plt.show()` (notebook) and
a path means `savefig` + `plt.close(fig)` (script). Notebooks reach in via
`sys.path.insert(0, '..')` (training.ipynb cell 3) with no editable install,
and pass `data_path='../data/raw/Q1_data.csv'` to work around cwd. Notably
`eda.ipynb` imports **nothing** from `src` — it is pure pandas/seaborn on the
raw CSV; only `training.ipynb` consumes the package. The direction of travel
is EDA → constants in `src` → notebook re-imports `src`.

Docstrings are uniformly Google-style with `Args:`/`Returns:`/`Raises:` on
every public method including trivial `predict()` wrappers, and section
banners (`# ---- Stage 1: ... ----`) divide long classes.

Candidate for skeleton: **yes** — the `logger.info` + single-`print`-for-
report rule, `basicConfig` only in the orchestrator entry point, zero logging
in pure helpers, and `save_path=None → show / path → savefig` are all
one-line rules with immediate payoff for notebook/script dual use.

## Open questions for synthesis

1. `run_cv` (the leakage-free per-fold CV loop) lives only in
   `notebooks/training.ipynb`, never in `src/`. Is "the CV loop stays in the
   notebook" a deliberate assessment-weight boundary, or the single clearest
   gap to close in the skeleton? Cross-check against the production-weight
   project.
2. `data/processed/` holds stale `X.csv`/`y.csv` orphans from an earlier
   design, shipped in the zip despite `.gitignore` listing `data/processed/`.
   Does the skeleton need a "generated artifacts are disposable and
   gitignored" rule, or an explicit clean step?
3. `pyproject.toml` has **no** `[tool.*]` section and no dev dependency group
   — no ruff, no pytest, no formatter. Is zero tooling config the actual
   assessment-weight floor, or is a ~6-line `[tool.ruff]` block cheap enough
   to be non-negotiable?
4. `requires-python = ">=3.12"` vs `.python-version = 3.14` — deliberate
   (floor vs pinned dev version) or drift? Affects whether the skeleton pins
   one or both.
5. Two independent `random_seed=42` values (classifier and
   `TrainingPipeline`), never reconciled. Should the skeleton mandate a
   single seed source threaded from the entry point?
6. Three different `get_config()` implementation styles across three
   classifiers (stash-tuned-params / read-back-from-estimator /
   enumerate-attributes). Which one becomes the canonical skeleton idiom?
   The LightGBM `**self._tuned_params` version is shortest but requires
   `**model_kwargs` in `__init__`.
7. `use_cached=True` loads split CSVs but leaves `self.dp` unfitted, so no
   further `transform()` is possible. Is the skeleton's caching seam the
   splits (as here) or the fitted `DataPipeline` object?
8. `_SKEWED_COLS` freezes 61 data-derived column names into source, with
   `detect_skewed_columns()` as the documented regenerator. Is "freeze the
   derived list, ship the regenerator" a general rule worth naming, or
   specific to needing fold-invariant column sets?
