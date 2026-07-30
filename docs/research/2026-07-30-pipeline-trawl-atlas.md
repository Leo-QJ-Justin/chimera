# Pipeline Trawl — Atlas vault (stated best practices)

> Research artifact for chimera. Mined 2026-07-30 per the trawl plan
> (docs/specs/2026-07-30-pipeline-templates-trawl-plan.md, Pass 4). Source:
> the maintainer's Obsidian vault (read-only; nothing written). Role: the
> CROSS-CHECK — what the notes say is best practice, to be compared against
> what the project code does (Passes 1-3). All paths relative to the vault
> root.

## 1. Neural Network Helper Functions — the DL training harness seed

Path: `00 Notes/ML Models/Deep Learning/Foundations/Neural Network Helper Functions.md`
(205 lines, 10 numbered code blocks, no prose between them — a pure
copy-paste harness).

**Structure as written (numbered section headers are verbatim `# ===` banners):**

1. **Imports and Logging Setup** — `torch`, `torch.nn as nn`, `tqdm`,
   `logging`. Config is stdlib `logging` only (no MLflow, no `logging.yaml`):
   ```python
   logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s',
                       datefmt='%Y-%m-%d %H:%M:%S')
   ```
2. **Device Setup** — three-way cascade `cuda` → `mps` → `cpu`, then
   `logging.info(f"Using device: {device}")`. The `mps` branch means the
   stated default is Mac-aware.
3. **Training for One Epoch** — `run_one_epoch(model, loader, loss_fn,
   optimizer, device) -> (avg_loss, avg_acc)`. `model.train()`;
   `tqdm(loader, desc="Training", leave=False)`; **`optimizer.zero_grad()`
   is called AFTER the forward/loss, before `backward()`** (works, but
   unusual ordering); accumulates `total_loss += loss.item() *
   images.size(0)` and divides by `total_count` (sample-weighted, correct);
   accuracy via `torch.max(outputs, 1)`.
4. **Evaluation Function** — `evaluate_model(model, loader, loss_fn, device)
   -> (avg_loss, avg_acc)`. `model.eval()` + `torch.no_grad()`, same
   sample-weighted averaging, `tqdm(desc="Evaluating")`.
5. **Overfit Single Batch Sanity Check** — `sanity_check_overfit_batch(model,
   train_loader, device, num_iterations=100) -> bool`. Grabs
   `next(iter(train_loader))`, builds its **own** `torch.optim.Adam(lr=1e-3)`
   and `nn.CrossEntropyLoss()` internally, prints every 20 iters, returns
   `acc > 0.95` with the messages `"Model can overfit a single batch"` /
   `"Model cannot overfit - check your architecture/optimizer"`.
6. **Prediction (Full Dataset)** — `predict(model, loader, device) ->
   (all_preds, accuracy)`. `model.eval()`, `model.to(device)`, `no_grad`,
   `all_preds.extend(preds.cpu())`. Instantiates a `loss_fn` that is never
   used (marked `# optional` — dead code).
7. **Prediction (Single Batch)** — `predict_single_batch(model,
   batch_images, device) -> preds.cpu()`.
8. **Training Loop** — `train_model(model, train_loader, val_loader,
   criterion, optimizer, device, epochs=15) -> history`, where
   ```python
   history = {'train_loss': [], 'train_acc': [], 'val_loss': [], 'val_acc': []}
   ```
   and per epoch a single `logging.info` line: `Epoch [{e+1}/{epochs}] |
   Train Loss/Acc | Val Loss/Acc` at `.4f`. Bookended by
   `logging.info("Starting training...")` / `"Training complete."`.
9. **Model, Optimizer, Loss Setup** — `model = MultiClassifier().to(device)`,
   `nn.CrossEntropyLoss()`, `torch.optim.Adam(model.parameters(), lr=1e-4)`.
10. **Example Usage** — `train_model(...)` → print history → `predict(...)`
    for test accuracy → `evaluate_model(...)` on test loader "separately if
    needed".

**What the harness conspicuously does NOT have** (critical for the
cross-check): no checkpointing / `torch.save`, no early stopping, no
`best_val` tracking, no LR scheduler, no gradient clipping, no seeding, no
MLflow, no config object (hyperparameters are literals), no AMP, no
`state_dict` reload of the best epoch. Classification-only (hardcoded
`torch.max(outputs,1)` accuracy in every function) — regression/forecasting
would need a metric-injection seam.

Candidate for skeleton: **yes** — the direct seed for the DL training utils.
It needs to be *extended* rather than replaced: add
checkpoint/early-stop/scheduler/seed/MLflow hooks and a metric callable,
keep the function names and the `history` dict contract, keep the
overfit-single-batch sanity check as a first-class util (the one distinctive
thing here).

## 2. Neural Networks — Architecture, Training & Optimisation (skim)

Path: `00 Notes/ML Models/Deep Learning/Foundations/Neural Networks —
Architecture, Training & Optimisation.md` (291 lines). Mostly theory.
Training-practice prescriptions that survive:

- **LR schedules described but never prescribed**: table of Fixed / Stepwise
  Decay / Exponential / Cyclical with pros-cons; no recommended default, no
  `torch.optim.lr_scheduler` code.
- **No early stopping and no checkpointing anywhere in the note** — grep
  confirms zero mentions of early stop / patience / checkpoint / gradient
  clipping. A real gap, not a mining miss.
- Hard rules worth encoding as lint/asserts: "Never use Linear in hidden
  layers", "Never use Softmax in hidden layers", "ReLU is the default for
  hidden layers", sigmoid in deep hidden layers → vanishing gradients
  (`0.25⁵ ≈ 0.001`).
- **Init pairing rule**: Xavier/Glorot for sigmoid/tanh/softmax; **He for
  ReLU/LeakyReLU/ELU/GELU** (fan_in only, compensates for ReLU zeroing ~50%
  of activations).
- **Standard layer order** (verbatim): `Fully Connected → Batch
  Normalization → Activation (ReLU) → Dropout`.
- Imbalance: class weights as the general default; Focal Loss for severe
  (1:1000); threshold adjustment as post-hoc; explicit **SMOTE caveat** —
  "controversial in research… can distort label distributions", cites
  *"SMOTE is what you don't need"*.

Candidate for skeleton: **partial** — the layer-order string and the
init/activation pairing belong in a model-builder helper; the LR-schedule
table is decision support, not code.

## 3. Logging with MLflow

Path: `00 Notes/Engineering & MLOps/Workflow & Reproducibility/Logging with
MLflow.md` (952 lines; PyTorch + Azure ML). The single richest prescriptive
note in the vault.

**The load-bearing pattern is a pair of custom wrappers, not raw MLflow
calls.** Signatures given verbatim in the note's Quick Reference:
```python
mlflow_log(mlflow_init_status: bool, log_function: str,  # "log_param"|"log_metric"|"log_artifact"
           key: str, value: Any, step: int = None,
           local_path: str = None, artifact_path: str = None)

mlflow_pytorch_call(mlflow_init_status: bool, pytorch_function: str, pytorch_model: nn.Module,
                    artifact_path: str, registered_model_name: str = None, step: int = None,
                    conda_env: dict = None, signature: ModelSignature = None,
                    input_example: np.ndarray = None, await_registration_for: int = 30)
```
The `mlflow_init_status` flag is stated as rule #1: *"Always use
`mlflow_init_status` flag — prevents crashes if MLflow isn't initialized;
allows graceful degradation in production."* The wrapper bodies are **not**
in the note — only the call signatures. A gap the skeleton must fill.

Other concrete prescriptions:
- Init: `mlflow.set_tracking_uri("file:./mlruns")` for local, `azureml://…`
  from env for cloud; `mlflow.set_experiment(...)`; `with
  mlflow.start_run(run_name="run-001") as run:` and capture
  `run.info.run_id`.
- **Config is a plain dict logged wholesale**: `config = {"learning_rate",
  "batch_size", "epochs", "seed", "optimizer", "loss_function"}` then a loop
  of `mlflow_log(..., "log_param", key, value)`. Plus
  `mlflow.log_param("device", str(device))`.
- Metrics logged with `step=epoch`, train and val separately ("to monitor
  overfitting"); `step` is "highly recommended".
- **Checkpoint contract** (verbatim, the stated save format):
  ```python
  torch.save({"epoch": epoch, "model_state_dict": model.state_dict(),
              "optimizer_state_dict": optimizer.state_dict(),
              "train_loss": train_loss, "val_loss": val_loss,
              "val_accuracy": val_accuracy}, checkpoint_path)
  ```
  Cadence: `if (epoch + 1) % 5 == 0`, path
  `./models/checkpoint_epoch_{epoch+1}.pt`, `os.makedirs("./models",
  exist_ok=True)`, then log as artifact under `artifact_path="checkpoints"`.
  **Periodic-N, not best-val-loss** — no "best checkpoint" concept.
- **Artifact folder taxonomy** (prescribed twice): `plots/`, `predictions/`,
  `checkpoints/`, `configs/`.
- Final model: always with `infer_signature(...)` + `input_example`, plus
  `registered_model_name` for production; semantic versioning of registry
  entries (v1.0.0 / v1.1.0 / v2.0.0).
- Run-name convention: `"mnist_v2_lr0.001_bs64"`; experiment names like
  `"mnist_baseline"` / `"mnist_with_augmentation"`.
- Timing table: hyperparams at start, metrics every epoch, checkpoints every
  N, final model + test metrics + plots at end.
- Azure: `.env` (`MLFLOW_TRACKING_URI`, `AZURE_TENANT_ID/CLIENT_ID/
  CLIENT_SECRET`) via `python-dotenv`, or a `config.yaml` with `mlflow:` +
  `azure:` blocks; `DefaultAzureCredential()` for managed identity; secrets
  never in code.
- An 11-item production checklist closes the note (all hyperparams logged,
  both train+val metrics, periodic checkpoints, signature+input_example,
  organised artifacts, registry, descriptive run names, error handling for
  failed MLflow ops, logging must not slow training).

Candidate for skeleton: **yes** — highest priority. The `mlflow_log` /
`mlflow_pytorch_call` wrappers with `mlflow_init_status` are the house style
and should be implemented (not just called) in the utils, together with the
`torch.save` dict schema and the four-folder artifact layout.

## 4. Reproducibility

Path: `00 Notes/Engineering & MLOps/Workflow & Reproducibility/Reproducibility.md`
(72 lines). Tight and fully prescriptive — effectively a `set_seed(seed)`
util waiting to be written:
```python
random.seed(seed); np.random.seed(seed)
torch.manual_seed(seed); torch.cuda.manual_seed(seed); torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
os.environ['PYTHONHASHSEED'] = str(seed)
```
Default `seed = 42` (the MLflow note uses `seed: 1111` — inconsistent
defaults across notes). Enumerated randomness sources include **DataLoader
worker RNGs / explicit `torch.Generator`s**, though no `worker_init_fn` /
`generator=` code is given — a gap. Stated caveats: deterministic cuDNN can
slow training and can raise for ops lacking deterministic impls; "omitting
one source can break repeatability".

Candidate for skeleton: **yes** — verbatim as `set_seed(seed: int)`, with
the missing DataLoader `generator`/`worker_init_fn` piece added.

## 5. Pre-Commit Hooks

Path: `00 Notes/Engineering & MLOps/Workflow & Reproducibility/Pre-Commit Hooks.md`
(345 lines).

Central prescription: a **two-tier stage split** — fast checks at
`[pre-commit]`, slow checks at `[pre-push]`. The "Real Example Breakdown" is
a ready-to-ship config:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.10
    hooks:
      - id: ruff-check
        args: [--fix]
        stages: [pre-commit]
      - id: ruff-format
        stages: [pre-commit]
  - repo: local
    hooks:
      - id: pyright
        entry: conda run -n dynamic-simu-model pyright
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
        stages: [pre-push]
      - id: pytest        # same shape as pyright
```
Notable: **Ruff (check+format) is the linter/formatter of record, Pyright
the type checker, pytest at pre-push**, and local hooks are wrapped in
`conda run -n <env>`. Install requires both `pre-commit install` **and**
`pre-commit install --hook-type pre-push`. Also documents `exclude:
"^(tests/|migrations/)"` and a Black/mypy alternative in the
quick-reference.

Candidate for skeleton: **yes** — drop-in `.pre-commit-config.yaml`, but the
`conda run -n <env>` entry is project-specific and the uv note (§9) implies
`.venv`, so the env-activation prefix must be parameterised.

## 6. CI-CID Gitlab Configurations

Path: `00 Notes/Engineering & MLOps/Workflow & Reproducibility/CI-CID Gitlab
Configurations.md` (339 lines). GitLab-specific (not GitHub Actions).

- **Stage sequence for ML** stated twice: `build → test → build-images →
  deploy-train → check → deploy-inference`.
- Job snippets worth keeping: `ruff check .` in `test`; `pytest -q` with
  `artifacts: {when: always, reports: {junit: report.xml}}`; `docker:dind`
  build that `docker save`s to `ml-model.tar` as a job artifact.
- **Pipeline gating on the model registry**: a `cron-check` job queries
  MLflow for the latest registered model version and **cancels the pipeline
  if the current model is up to date**. Companion `pull-model` /
  `upload-model` jobs move artifacts.
- Container data triad: **volume → volumeMount → symlink**, with `ln -s
  /data/workspaces/myproject/data /app/data` before `python train_model.py`
  so mounted data appears at the program-expected path without copying.
- Strategy list: centralise config in pipeline-level `variables:`, reuse
  `include: component:` templates, pass artifacts explicitly via `artifacts`
  + `needs`, branch/schedule-conditional triggers, CI/CD variables for
  secrets, FastAPI-on-Cloud-Run inference with min/max instances.

Candidate for skeleton: **partial** — the stage taxonomy and the
MLflow-registry gating job are reusable ideas; the concrete YAML is
GitLab/Cloud-Run-bound and needs translating if real projects use GitHub.

## 7. Containerization with Docker

Path: `00 Notes/Engineering & MLOps/Workflow & Reproducibility/Containerization
with Docker.md` (272 lines). Framed around **Streamlit** serving, not
training.

- Dockerfile pattern: `FROM python:3.12-slim`, `WORKDIR /app`, **copy
  `requirements.txt` first then `COPY . /app`** for layer caching, `ENV
  PYTHONPATH=/app`, `EXPOSE 8501`, optional `VOLUME /data`, `CMD
  ["streamlit","run","app.py"]`. (The snippet has a literal typo:
  `"app.py""`, and an inline comment after `EXPOSE 8501` that would break
  the build.)
- **Port-matching rule stated as a hard invariant** across four places:
  Dockerfile `EXPOSE` = Streamlit `--server.port` = container side of `-p
  host:container` = socat target.
- Shared-infra access via socat: `socat TCP-LISTEN:8501,fork
  TCP:cpubox:8013 &` (needs a second terminal). Port conflicts: increment
  host port by +100; only touch containers you own.
- Production rules: **never `ENV API_KEY=` in the Dockerfile** (use `-e` at
  runtime / Compose secrets); minimal base images; non-root via `adduser
  --disabled-password --gecos '' appuser` + `USER appuser`; combine
  `apt-get update && install && rm -rf /var/lib/apt/lists/*` into one
  layer; `.dockerignore` = `__pycache__ *.pyc .git .env node_modules
  .DS_Store`; pin tags not `latest`; `--memory=512m --cpus=0.5`; `--gpus
  all` for GPU.

Candidate for skeleton: **partial** — the `.dockerignore`, layer-ordering,
non-root and no-secrets rules generalise; the Streamlit/socat specifics
belong in a serving skeleton, not a training one. Nothing here covers
containerising a *training* job (that lives in the CI note).

## 8. nbqa package for formatting and linting

Path: `00 Notes/Engineering & MLOps/Workflow & Reproducibility/nbqa package
for formatting and linting.md` (120 lines).

`pip install -U nbqa "nbqa[toolchain]"`; usage `nbqa <tool>
<notebook.ipynb>`; `nbqa black notebook.ipynb --line-length=88`, `nbqa
flake8`, `nbqa isort my_notebook.ipynb --float-to-top`. Config hoisted into
`pyproject.toml` (`[tool.black] line-length = 88`). Pre-commit block:
```yaml
- repo: https://github.com/nbQA-dev/nbQA
  rev: v1.9.1
  hooks:
    - id: nbqa-black
    - id: nbqa-flake8
```
**Conflict flag:** this note's toolchain is **black + flake8 + isort**,
while §5 prescribes **Ruff**. The two notes disagree on the
formatter/linter of record.

Candidate for skeleton: **partial** — include the nbQA pre-commit block only
if notebooks are in scope, and reconcile to one of Ruff *or* black/flake8
(`nbqa-ruff` exists and would resolve it).

## 9. Working with Virtual Environments and importing packages

Path: `00 Notes/Engineering & MLOps/Workflow & Reproducibility/Working with
Virtual Environments and importing packages.md` (144 lines).

Three-part note: conda commands, a short git essentials block, and **uv** as
the modern path: `pipx install uv`; `uv init` → creates `pyproject.toml` +
`.venv`; `uv venv -p 3.11`; `uv add <pkg>`; `uv sync`; `uv pip install -r
requirements.txt`. Jupyter kernel registration prescribed explicitly:
```bash
uv pip install ipykernel
python -m ipykernel install --user --name="<env-name>" --display-name="Python (<Project>)"
```
Candidate for skeleton: **partial** — `uv init`/`uv sync` + `pyproject.toml`
is the stated modern default and should drive the skeleton's env bootstrap,
but conda is still documented and §5's hooks assume `conda run`. Pick one.

## 10. Cross-Validation

Path: `00 Notes/ML Methods & Workflow/Evaluation/Cross-Validation.md` (544
lines; contains **two overlapping guides concatenated**).

Prescriptions, not theory:
- **Nested CV is the stated default for honest model-family comparison.**
  Canonical snippet: `inner_cv = KFold(3, shuffle=True, random_state=1)`,
  `outer_cv = KFold(5, shuffle=True, random_state=1)`,
  `cross_val_score(GridSearchCV(est, grid, cv=inner_cv), X, y, cv=outer_cv)`.
- A **manual nested loop variant** given specifically so
  `best_params_per_fold` can be recorded — "Track best parameters per outer
  fold if you want to inspect tuning stability".
- Mapping table: outer-train ↔ train, outer-test-per-fold ↔ validation,
  aggregated outer scores ↔ test.
- **Deployment recipe (Option A, "recommended")**: nested CV confirms the
  model *family*; then run a full search on the **entire dataset** and fit
  the final model on all data; report the nested-CV number as expected
  generalisation, separately from the fitted artifact. Option B (external
  holdout touched once) is the fallback.
- Hard rule: **"Never reuse the same CV scores that selected hyperparameters
  as your final unbiased performance metric."**
- Compute escape hatch: plain train/val/test with test used exactly once,
  "accept higher variance".
- `random_state` is hardcoded (0 or 1) in every splitter — seeding is
  treated as part of the CV contract.

Candidate for skeleton: **yes (tabular/sklearn path)** — nested-CV
evaluation util + "final fit on full data" step. Caveat: **all of it is
`KFold`/`shuffle=True`, i.e. i.i.d.** No `TimeSeriesSplit`, no walk-forward,
no grouped CV anywhere in the note — yet both project specs (§13) use
expanding-window walk-forward. Direct conflict.

## 11. Hyperparameter Tuning

Path: `00 Notes/ML Methods & Workflow/Evaluation/Hyperparameter Tuning.md`
(358 lines). §1-3 are textbook. §4-5 are the valuable part: **Hydra Sweeper
+ Optuna**, the stated config-driven-tuning mechanism.

```yaml
defaults:
  - override hydra/sweeper: optuna
  - override hydra/sweeper/sampler: tpe
hydra:
  sweeper:
    study_name: "image-classification"
    storage: null
    direction: "minimize"
    n_trials: 20
    n_jobs: 1
    sampler: {seed: 123}
    params:
      lr: tag(log, interval(1e-3, 1e-2))
      gamma: choice(0.7, 0.8, 0.9)
      epochs: range(5, 10)
```
- Search-space DSL documented: `range(start,stop,step)`, `choice(...)`,
  `interval(a,b)`, `tag(log, ...)`.
- Custom space via `custom_search_space: my_module.configure` with
  `def configure(cfg, trial): trial.suggest_float("dropout", 0.1, 0.5)`.
- CLI form: `python my_script.py --multirun 'lr=interval(1e-3,1e-2)'
  'gamma=choice(0.7,0.8,0.9)'`.
- **Hard constraint worth encoding**: Hydra's Optuna sweeper supports only
  **TPE, Random, CmaEs, NSGAII**; Grid/QMC/BoTorch/PartialFixed/BruteForce
  are **not** supported — a custom sweeper is required otherwise.
- Selection rule of thumb: high-dimensional → Randomized; low-dimensional →
  Grid.

Candidate for skeleton: **yes** — the sweeper YAML plus the "each multirun
iteration becomes its own MLflow run" idea (stated in the second project
spec, §13) is the config-driven tuning backbone.

## 12. Model Evaluation

Path: `00 Notes/ML Methods & Workflow/Evaluation/Model Evaluation.md` (575
lines). Largely textbook metric definitions. Prescriptive residue:

- **Metric pairing rule**: "Use MAE in conjunction with RMSE… if RMSE > MAE,
  the model is making some significantly larger errors on certain
  predictions." Good default for a regression-metrics util.
- Accuracy only valid for balanced classes (highlighted); F1 for uneven
  distributions; default classification threshold 0.5 called out as one
  arbitrary operating point, motivating ROC sweep.
- **Error-analysis util worth lifting verbatim** — normalised,
  diagonal-zeroed confusion matrix:
  ```python
  row_sums = cm.sum(axis=1, keepdims=True)
  norm_cm = cm / row_sums
  np.fill_diagonal(norm_cm, 0)   # only interested in misclassifications
  ```
  With a stated error taxonomy: class-level imbalance → rebalance/add data;
  feature-range/boundary errors → model capacity or split criteria; random
  errors across classes → data quality (label noise, weak features). Stated
  limitation: the CM "provides no link to feature values, so it cannot
  reveal boundary-related weaknesses".

Candidate for skeleton: **partial** — the metrics-dict shape
(`{"MAE","MSE","RMSE","R²"}`, matching §13's `_evaluate_model`) and the
normalised-CM helper are worth extracting; the rest is reference reading.

## 13. Data Engineering — End-to-end Pipelines

Path: `00 Notes/Data Engineering/Data Pipelines & Formats/Data
Engineering-End-to-end Pipelines.md` (735 lines). **The canonical
classical-ML pipeline skeleton in note form** — near-complete, class-based,
config-driven.

Stated repo layout (flat, minimal):
```
root/  eda.ipynb  main.py  README.md  requirements.txt
  data/data.csv
  src/{data_preparation.py, model_training.py, config.yaml}
```
Note `config.yaml` lives **inside `src/`**, and there is no `tests/`, no
`configs/` dir, no `outputs/`.

Modularisation doctrine: extract from notebook → define functions/classes →
split into `data_preparation.py`, `model_training.py`, `main.py`. Every
function/class carries a Google-ish docstring with type hints, and the note
prescribes an idiosyncratic **underline-length convention**: `Attributes:` +
11-12 dashes, `Args:` + 5 dashes, `Returns:` + 8 dashes. Private helpers get
a leading underscore; pure helpers are `@staticmethod`.

- **`DataPreparation(config: Dict[str, Any])`** — `__init__` sets
  `self.config` and eagerly builds `self.preprocessor =
  self._create_preprocessor()`. `clean_data(df) -> pd.DataFrame` brackets
  its body with `logging.info("Starting data cleaning")` / `"…completed."`.
  `_create_preprocessor() -> ColumnTransformer` composes three `Pipeline`s
  (`StandardScaler`; `OneHotEncoder(handle_unknown="ignore")`;
  `OrdinalEncoder(categories=…, handle_unknown="use_encoded_value",
  unknown_values=-1)`) into `ColumnTransformer(transformers=[("num",…),
  ("nom",…), ("ord",…), ("pass","passthrough",…)], remainder="passthrough",
  n_jobs=-1)`, with feature lists read from config keys
  `numerical_features` / `nominal_features` / `ordinal_features` /
  `passthrough_features`.
- **`ModelTraining(config, preprocessor)`** — `split_data` does a two-stage
  `train_test_split` (`test_size=config["val_test_size"]` then
  `config["val_size"]` on the temp half) with `random_state=42` hardcoded in
  both calls. `train_and_evaluate_baseline_models(...)` loops a
  `{"linear_regression","ridge","lasso"}` dict, wrapping each in
  `Pipeline([("preprocessor", self.preprocessor), ("regressor", model)])` —
  **preprocessor inside the pipeline, so no fit-transform leakage**.
  `train_and_evaluate_tuned_models(...)` wraps the same pipeline in
  `GridSearchCV(pipeline, param_grid, cv=cv, scoring=scoring, n_jobs=-1)`
  with grid/cv/scoring all from config. `_evaluate_model` /
  `evaluate_final_model` both return `{"MAE","MSE","RMSE","R²"}` and log
  each metric line by line.
- **`main.py`** — `logging.basicConfig(level=logging.INFO)`;
  `@ignore_warnings(category=Warning)` on `main()`; `config_path =
  "./src/config.yaml"` opened with `yaml.safe_load`;
  `pd.read_csv(config["file_path"])`; then prep → split → baselines → tuned
  → `all_models = {**baseline_models, **tuned_models}` →
  **`best_model_name = max(all_metrics, key=lambda k:
  all_metrics[k]["R²"])`** → `evaluate_final_model` on the test set.
  Guarded by `if __name__ == "__main__":`.
- **`config.yaml`** carries `file_path`, `target_column`, `val_test_size`,
  `val_size`, `param_grid` (with `regressor__alpha` double-underscore
  pipeline addressing), `cv`, `scoring`, the four feature lists, and
  category orderings.
- **`requirements.txt` via `pip list --format=freeze`**, then manually
  pruned to directly-used packages.
- **README spec (9 required sections)**: title/description;
  prerequisites+install; how to run `main.py` and modify `config.yaml`;
  logical pipeline steps; EDA key findings; feature-handling **summarised
  in a table**; model choice rationale; model evaluation incl. *why* the
  metric was chosen; deployment considerations.

Candidate for skeleton: **yes — the primary one for tabular/classical ML.**
Directly transplantable. Gaps to fill: **no MLflow at all** (plain `logging`
only), no model persistence (`best_model` is found and evaluated but never
saved), `random_state=42` hardcoded rather than config-driven, no `tests/`,
single hold-out rather than the nested CV that §10 insists on.

## 14. Project design specs — how projects get scoped

Path: `docs/superpowers/specs/2026-05-08-singapore-trade-vulnerability-design.md`
(199 lines). Scoping is **citation-gated**: a "Key Design Decisions (All
Citable)" table pairs every methodological choice with a reason *and* a
published citation (PPML per Santos Silva & Tenreyro 2006; SHAP per
Lundberg & Lee 2017; expanding-window CV as "standard ML practice"), and one
row records a *dropped* citation because the PDF 403'd. Scope is fenced with
explicit **In scope / Out of scope / Stretch goal** lists, followed by
numbered, quantified **Success Criteria** ("≥5 products flagged", "higher
Spearman ρ than naive persistence in ≥3 of 6 expanding-window folds", "same
3-5 features in top 5 by mean |SHAP| across ≥3 of 6 folds") and a full repo
tree (`src/data/`, `src/models/`, `notebooks/01_…`, `outputs/figures/`,
`pyproject.toml`, `.gitignore` ignoring `data/raw/, data/processed/,
plans/`, `CLAUDE.md`).

Path: `docs/superpowers/specs/2026-06-10-usep-forecast-design.md` (269
lines). Scoping is **phase-gated and EDA-gated**: three phases (STL+ARIMA →
STL+XGBoost hybrid → LSTM autoencoder) sharing one evaluation framework,
with naïve baselines established *before* Phase 1; time-based split (train
2018-2022 / val 2023 / test 2024-2025) with an explicit walk-forward
protocol and "test touched once"; fixed 5-step preprocessing incl. a
hardcoded regulatory ceiling (MPC 4500 SGD/MWh) as the validation gate and
"do not remove spikes — they are anomaly targets"; a table binding each EDA
analysis to the decision it informs, with the rule that **EDA conclusions
gate all feature engineering — "no feature choices are prescribed in
advance"**; and an explicit Open Questions section that *defers repo
structure to project init*. Its §4 is the most complete MLOps prescription
in the vault: one MLflow experiment per phase; tuning runs tagged
`run_type=tuning` logging RMSE/MAPE as "ranking signal for model selection
only"; a single run tagged `final_evaluation=true` logging seven diagnostic
tests (unbiasedness t-test, Ljung-Box, Mincer-Zarnowitz with HAC, OOS R² vs
naïve, RMSE/MAE/MAPE/Bias, Diebold-Mariano vs persistence *and* vs prior
phase, ARCH-LM) plus a fixed artifact list; and a **model registry rule —
"inference script and Streamlit dashboard always pull from the registry,
never from a raw run"**. Tech stack fixes `hydra-core` for config with a
`configs/config.yaml` + `configs/model/*.yaml` + `configs/anomaly/*.yaml`
hierarchy ("base config holds paths, split dates, MLflow URI; phase configs
override only what changes"), Python 3.11+, pytest, and `outputs/`
gitignored.

Candidate for skeleton: **yes** — the USEP spec is effectively the target
architecture for the reusable skeleton (Hydra config hierarchy +
one-experiment-per-phase MLflow + registry-only inference +
`data/{raw,processed,splits}`). The trade spec supplies the repo-tree and
scope-fencing template.

## Open questions for synthesis

Prescriptions most likely to diverge from what the real project code does:

1. **MLflow wrapper bodies don't exist in the notes.** `mlflow_log` /
   `mlflow_pytorch_call` are only ever *called*; the note gives signatures,
   not implementations. If the real code has these functions, they are the
   ground truth and should be lifted verbatim. If not, the whole
   `mlflow_init_status` pattern may be aspirational.
2. **Checkpointing is periodic-N, never best-val.** Both the MLflow note and
   the NN harness (nothing at all) omit best-checkpoint tracking and early
   stopping. Real training code almost certainly tracks a best val metric —
   expect divergence and decide which wins.
3. **The NN harness has no MLflow, no seeding, no config.** The DL note and
   the MLflow note were written independently; merging them is the main
   synthesis job, and the real code likely shows how they were actually
   joined.
4. **i.i.d. CV vs walk-forward.** `Cross-Validation.md` prescribes nested
   `KFold(shuffle=True)` and calls it required for fair comparison; both
   project specs use expanding-window walk-forward and one explicitly says
   random split is invalid for time series. Is nested CV the tabular-only
   default, or is the note out of date relative to the forecasting work?
5. **"Fit the final model on the entire dataset"** (Cross-Validation Option
   A) contradicts the USEP spec's "test touched once, 2024-2025 never
   trained on". Two incompatible deployment doctrines.
6. **Config mechanism: raw `yaml.safe_load` vs Hydra.** The end-to-end
   pipeline note opens `./src/config.yaml` by hand; the tuning note and
   USEP spec mandate Hydra with a `configs/` hierarchy and CLI overrides.
   Which does the real code use, and does the skeleton need both paths?
7. **Repo layout: three competing trees.** `src/ + config.yaml inside src/,
   no tests/` (pipelines note) vs `src/data/ + src/models/ + notebooks/ +
   outputs/` (trade spec) vs `configs/ + data/{raw,processed,splits}/ +
   notebooks/` with layout explicitly deferred (USEP spec).
8. **Linting toolchain conflict**: Ruff (pre-commit note) vs
   black/flake8/isort (nbqa note). Also env conflict: `conda run -n <env>`
   in the hook entries vs uv/`.venv` as the stated modern default.
9. **Seed value inconsistency**: 42 (Reproducibility, and hardcoded in the
   pipelines note's splits) vs 1111 (MLflow note config). And seeds are
   hardcoded in the pipeline templates rather than read from config, which
   contradicts "log all hyperparameters including seed".
10. **No model-artifact persistence in the classical pipeline.** `main.py`
    selects a best model by R² and evaluates it, then exits without saving.
    If the real code saves via joblib/pickle/MLflow, that seam is
    undocumented in the notes.
11. **Determinism cost is acknowledged but not gated.**
    `cudnn.deterministic=True` + `benchmark=False` is prescribed
    unconditionally; real training code may toggle it. Worth a config flag
    in the skeleton.
12. **Classification-only assumptions in the DL harness**
    (`torch.max(outputs,1)` accuracy baked into five functions) vs the
    forecasting/regression work — the metric computation needs to become
    injectable.
