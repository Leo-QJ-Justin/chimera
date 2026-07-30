# Pipeline Trawl — all-assignments (AIAP coursework)

> Research artifact for chimera. Mined 2026-07-30 per the trawl plan
> (docs/specs/2026-07-30-pipeline-templates-trawl-plan.md, Pass 2). Source:
> `~/all-assignments`, branches `origin/qjjustin_leo` (the maintainer's),
> `origin/li_yang_chew`, `origin/dengfeng_zhou`, and `origin/main` (the
> unfilled scaffold). All findings are static reads via `git show` /
> `git diff`; nothing was executed.

## 0. Framing correction that changes how to read everything below

The plan assumed the three branches "filled in the same scaffold" and that
divergence is the signal. True — but the stronger signal is the
**scaffold/fill-in boundary**, which is recoverable exactly: `origin/main`
holds the unfilled scaffold, so any file byte-identical to main is
**AISG-authored canon**, and any file that differs is a trainee's fill-in.

```
git rev-parse origin/{qjjustin_leo,li_yang_chew,dengfeng_zhou,main}:assignment3/src/mnist/general_utils.py
→ 40c89deb1565bc232c79aa4c2de71a9cad7ce303  (all four identical)
```

So `general_utils.py` — the file the plan guessed was "likely origin of the
house style" — is **not the maintainer's**. It is AISG's, unmodified by
anyone. That makes it the highest-confidence canon in the whole trawl, and
it means the maintainer's own style must be read from a much smaller set.

`git diff --stat origin/main origin/qjjustin_leo -- assignment3/` gives the
maintainer's actual authorship: `conf/process_data.yaml`,
`conf/train_model.yaml` (sweeper block only), `src/process_data.py`,
`src/train_model.py` (+69/-0, additions only),
`src/mnist/modeling/models.py`, all four `mnist_fastapi/*`,
`mnist_streamlit/app.py`, `Containerfile`.

Everything else in Pass A — `conf/logging.yaml`, `conf/batch_infer.yaml`,
`src/batch_infer.py`, `src/mnist/modeling/utils.py`,
`data_prep/datasets.py`, `data_prep/transforms.py`, `src/mlflow_test.py`,
`pyproject.toml`, root `.gitlab-ci.yml` — is untouched canon.

**Practical consequence for skeletons:** canon files can be lifted verbatim
with high confidence (three independent trainees and the course authors all
left them alone). Fill-in files are student work of uneven quality and must
be judged on merit, not copied for authority. Every pattern below is
labelled `[CANON]` or `[FILL-IN]`.

## 1. `conf/logging.yaml` — JSON-lines rotating logs, five handlers `[CANON]`

`origin/main` = `origin/qjjustin_leo:assignment3/conf/logging.yaml`.
`pythonjsonlogger.jsonlogger.JsonFormatter`, one console handler plus four
`RotatingFileHandler`s split by level (debug/info/warn/errors), each 10 MB ×
20 backups, `delay: True`, root at INFO fanning out to all five.

```yaml
formatters:
  json:
    format: "%(asctime)s %(process)d %(name)s %(levelname)s %(message)s"
    class: pythonjsonlogger.jsonlogger.JsonFormatter
    datefmt: "%Y-%m-%dT%H:%M:%S%z"
```

`%(process)d` and ISO-8601 `datefmt` with `%z` are deliberate: shaped for
container log shipping, where PID disambiguates workers and offset-aware
timestamps survive aggregation. `delay: True` matters in read-only
containers — no file is created until something is actually logged.

Evolution in `assignment6/conf/logging.yaml`: identical except every file
handler gains `mode: "w"`. That truncates per run, which **conflicts with
`RotatingFileHandler`'s purpose** — rotation implies retention, `mode: "w"`
throws it away. Reads as convenience during iterative timeseries work, not
an improvement.

Candidate for skeleton: **yes** — lift a3 version verbatim, four-level split
included; cheap, and the level-partitioned files genuinely help triage. Do
not carry `mode: "w"` forward.

## 2. `setup_logging` — YAML dictConfig with runtime log-dir rebinding `[CANON]`

`assignment3/src/mnist/general_utils.py`:

```python
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            for handler in log_config["handlers"].values():
                if "filename" in handler:
                    filename = os.path.basename(handler["filename"])
                    handler["filename"] = os.path.join(log_dir, filename)
        logging.config.dictConfig(log_config)
    except Exception as error:
        logging.basicConfig(format="...", level=default_level)
        logger.error("Logging config file is not found. Basic config is being used.")
```

Two ideas worth keeping. First, handler filenames are **rewritten at load
time** by basename, so the YAML stays environment-agnostic and the caller
redirects logs without templating the config. Second, config failure
**degrades to `basicConfig` rather than dying** — correct for a logging
bootstrap, since crashing on a missing log config is strictly worse than
logging to stderr.

Caveat if lifted: the `except` catches bare `Exception` and reports every
failure as "config file is not found", so a malformed-YAML error is
misreported. Widen the message or split `FileNotFoundError` from the rest.

Candidate for skeleton: **yes** — the log-dir rebinding trick and the
degrade-don't-die posture are both directly reusable; fix the error message
on the way in.

## 3. Hydra entry-script shape `[CANON skeleton, FILL-IN body]`

Every entry script — a3 `train_model.py`, `process_data.py`,
`batch_infer.py`, and a6 `ml_experiment.py` — is `@hydra.main` +
`main(args)` + `if __name__ == "__main__": main()`. No argparse, no env-var
config reading anywhere in the training path. Config name carries the
`.yaml` suffix in the decorator (`config_name="train_model.yaml"`), which
Hydra tolerates.

The canonical logging bootstrap inside a Hydra main, from scaffold
`train_model.py`:

```python
    logger = logging.getLogger(__name__)
    mnist.general_utils.setup_logging(
        logging_config_path=os.path.join(
            hydra.utils.get_original_cwd(), "conf", "logging.yaml"
        ),
        log_dir=args.get("log_dir", None),
    )
```

`hydra.utils.get_original_cwd()` is the load-bearing detail: Hydra chdirs
into a per-run output dir, so a relative `./conf/logging.yaml` resolves
differently inside `main` than outside. This is the single most
transplantable idiom in the repo and also the one all three trainees handled
inconsistently (see §8).

`batch_infer.yaml` opts out of the chdir entirely:

```yaml
hydra:
  job:
    chdir: False
```

Candidate for skeleton: **yes** — `@hydra.main` +
`get_original_cwd()`-anchored logging setup + `args.get("key", default)` for
optional keys is the house style, attested across two assignments and all
three branches.

## 4. MLflow wrapper pair — `mlflow_init` / `mlflow_log` `[CANON]`

`general_utils.py` exposes three functions: `mlflow_init(...) ->
(init_success, mlflow_run, step_offset)`, `mlflow_log(mlflow_init_status,
log_function, **kwargs)`, and `mlflow_pytorch_call(...)`.

The design intent is **MLflow-optional pipelines**: `mlflow_init` returns a
boolean, every call site passes that boolean, and `mlflow_log` no-ops when
it's false. Training runs unchanged with no tracking server. Both loggers
swallow exceptions — tracking failures never break training.

Dynamic dispatch with signature filtering:

```python
        method = getattr(mlflow, log_function)
        method(**{key: value for key, value in kwargs.items()
                  if key in method.__code__.co_varnames})
```

**This idiom is actively dangerous and is the sharpest finding of the
trawl.** A misspelled or wrong-named kwarg is silently dropped rather than
raising `TypeError`, and the surrounding `except Exception:
logger.error(...)` swallows the resulting arity error. It converts typos
into silent no-logging. It bit a peer for real — §8.1.

Run-naming and orchestration hooks, also canon:

```python
            if "MLFLOW_HPTUNING_TAG" in os.environ:
                run_name += "-hp"
            ...
            set_tag("MLFLOW_HPTUNING_TAG", "hptuning_tag")
            set_tag("JOB_UUID")
            set_tag("JOB_NAME")
```

Runs get `-{int(time.time())}` appended for uniqueness; `JOB_UUID`/`JOB_NAME`
come from the Run:AI/K8s job env. So env vars *do* appear — not for config,
only for **orchestration provenance tagging**. Worth preserving: it's how a
run in the UI gets traced back to a cluster job.

`resume=True` searches `tags.mlflow.runName LIKE '{base_run_name}-%'`
ordered by start_time, reattaches, then walks `get_metric_history` for every
non-`system/` metric to compute `step_offset` — so resumed runs continue the
step axis instead of overwriting from zero. `train_model.py` consumes it as
`range(step_offset + 1, args["epochs"] + step_offset + 1)`. Sound idea; the
implementation carries three nested `try/except AttributeError` layers
guessing at MLflow API versions — version-coupling to delete, not copy.

Candidate for skeleton: **partial** — keep the init/log/optional-tracking
contract, the `-hp` suffix, and the orchestration tags. **Replace the
`co_varnames` filtering with plain kwargs passthrough** so mistakes surface.
Reimplement step-offset resume against one pinned MLflow version.

## 5. Checkpointing `[CANON]`

Provided verbatim in `train_model.py` (the maintainer's diff is +69/-0, so
this block is untouched scaffold):

```python
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "optimiser_state_dict": optimiser.state_dict(),
                    "train_loss": curr_train_loss,
                    "test_loss": curr_test_loss,
                },
                model_checkpoint_path,
            )
```

Dict-with-optimiser-state (not bare `state_dict`), gated on `epoch %
args["model_checkpoint_interval"] == 0`, written to a **fixed**
`models/model.pt` — so checkpoints overwrite; only the latest survives
locally, and MLflow artifacts are the actual history. Note the British
`optimiser` spelling throughout, consistent across the codebase.

The matching loader in `modeling/utils.py` is the more reusable half — it
accepts three checkpoint shapes:

```python
    if isinstance(checkpoint, torch.nn.Module):
        loaded_model = checkpoint
    else:
        loaded_model = mnist.modeling.models.Net()
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            loaded_model.load_state_dict(checkpoint["model_state_dict"])
        else:
            loaded_model.load_state_dict(checkpoint)
```

Full pickled module / wrapped dict / bare state_dict all load. Pragmatic
given MLflow's `log_model` and manual `torch.save` produce different shapes.
`weights_only=False` is a deserialization-trust assumption — fine for
self-produced checkpoints, wrong for anything downloaded.

Device selection is triplicated (`train_model.py`, `load_model`, and a6)
with the same cuda→mps→cpu ladder, negated-flag style (`no_cuda`/`no_mps` in
training, positive `use_cuda`/`use_mps` in inference — the inconsistency is
canon's, not a trainee's).

Candidate for skeleton: **yes** for the save-dict shape and the three-shape
loader. **Partial** on the fixed filename: interval-checkpointing to a
single overwriting path loses history if MLflow is off, so parameterize with
an `{epoch}` slot.

## 6. `conf/` layout and the empty-file tell `[FILL-IN]`

Scaffold `origin/main:assignment3/conf/process_data.yaml` is **empty** —
that's why all three branches diverge on key naming, and it's the cleanest
natural experiment in the repo:

| branch | keys |
|---|---|
| qjjustin_leo | `raw_data_dir_path`, `processed_data_dir_path`, nested `logging: {logging_config_path, log_dir}` |
| li_yang_chew | `RAW_DATA_DIR_PATH`, `PROCESSED_DATA_DIR_PATH`, `LOG_DIR_PATH`, `logging_config_path` |
| dengfeng_zhou | nested `data: {raw_path, processed_path}` |

Canon elsewhere (`train_model.yaml`, `batch_infer.yaml`, both AISG-written)
is **flat `snake_case`**, so the maintainer's choice matches house style
while li_yang's SCREAMING_CASE (a config file styled like env vars) does
not. dengfeng's `data:` nesting is arguably cleanest but is the only one
that drops the logging config entirely — consistent with their different
logging bootstrap (§8.2).

`train_model.yaml` is canon apart from the sweeper block, and pairs Hydra
config with an Optuna sweeper in the same file:

```yaml
defaults:
  - override hydra/sweeper: optuna
  - override hydra/sweeper/sampler: tpe
hydra:
  sweeper:
    sampler: {seed: 55}
    direction: ["minimize", "maximize"]
    n_trials: 3
    params:
      lr: tag(log, interval(1e-3, 1e-2))
```

`direction: ["minimize", "maximize"]` is multi-objective and requires `main`
to return a matching tuple — which it does: `return curr_test_loss,
curr_test_accuracy`, with an inline comment tying it back. That
return-value/sweeper-direction coupling is easy to break and worth
documenting loudly in any skeleton.

Both peers replaced `tag(log, interval(1e-3, 1e-2))` with
`range(0.9,1.7,step=0.1)` and dropped the `epochs` sweep — a log-uniform
continuous search became a coarse grid. Given the base `lr: 1.0` for
Adadelta, the peers' range is arguably better centred, but the canon form is
the better teaching example.

Candidate for skeleton: **partial** — adopt flat snake_case, one YAML per
entry script, `logging.yaml` separate. Ship the Optuna block as opt-in and
comment the tuple-return coupling.

## 7. Config split by concern — new in assignment6 `[FILL-IN]`

a6 splits config into `train_model.yaml` (MLflow + training hyperparams) and
`ts_params.yaml` (per-feature time-series orders + feature-type lists):

```yaml
ts_params:
  pm2.5: {p: 44, q: 2}
  DEWP: {p: 0, q: 4}
numerical_features: []
nominal_features:
  - cbwd
ordinal_features: []
```

`Datapipeline.__init__(config_path=...)` reads it with plain
`yaml.safe_load` — **outside Hydra**, so a6 runs two parallel config
systems. It works but means `ts_params.yaml` gets no Hydra overrides, no
composition, no sweep access. Splitting run-params from domain-params is the
right instinct; bypassing Hydra to do it is not.

Candidate for skeleton: **partial** — keep the domain/run split, but express
it as a Hydra config group so both halves stay overridable.

## 8. Peer divergences worth stealing (and one worth quarantining)

Both peers changed the same 10 files; `general_utils.py`, `batch_infer.py`,
`modeling/utils.py`, `datasets.py`, `transforms.py` are untouched by
everyone.

**8.1 li_yang_chew: a silent-logging bug caused by canon's kwarg filter.**
In `train_model.py`:

```python
            mnist.general_utils.mlflow_log(
                mlflow_init_status, "log_artifact",
                artifacts = model_checkpoint_path
                )
```

`mlflow.log_artifact` takes `local_path`, not `artifacts`. The `co_varnames`
filter (§4) drops the kwarg, `log_artifact()` is called with zero args,
`TypeError` is caught and logged at error level, and **checkpoints are never
logged** while training reports success. The maintainer's
`local_path=model_checkpoint_path` is correct. Direct evidence that §4's
filtering idiom must not be copied as-is. Also in the same file:
`"test_bs": args.train_bs` — copy-paste, mislogs the param.

**8.2 dengfeng_zhou: better MLflow hygiene — steal this.** Three concrete
improvements over the maintainer's branch:

```python
            mnist.general_utils.mlflow_log(
                ... log_function="log_artifact",
                local_path=model_checkpoint_path,
                artifact_path=f"checkpoints/epoch_{epoch}"   # namespaced, not flat
            )
    mnist.general_utils.mlflow_pytorch_call(
        mlflow_init_status=mlflow_init_status,               # a3 fill-in hardcodes True
        pytorch_function="log_model", pytorch_model=model,
        name="mnist-model",
        input_example=np.random.rand(1, 1, 28, 28).astype("float32"),  # → signature
    )
```

`artifact_path=f"checkpoints/epoch_{epoch}"` recovers per-epoch history that
flat logging collapses. `input_example` lets MLflow infer a model signature
— real serving value. And the maintainer's branch has a genuine bug here:
`mlflow_pytorch_call(mlflow_init_status=True, ...)` is **hardcoded `True`**,
so model registration is attempted even when MLflow init failed, defeating
the optional-tracking contract; dengfeng threads the real flag. Steal all
three.

**8.3 dengfeng_zhou: required settings + compose env injection — steal
this.** `config.py` drops the defaults:

```python
    PRED_MODEL_UUID: str
    PRED_MODEL_PATH: str
```

Pydantic then **fails fast at import** if the env vars are absent, versus
the maintainer branch's hardcoded `PRED_MODEL_UUID = "cf018fea..."` and
`PRED_MODEL_PATH = "./models/model.pt"`, which will happily serve a stale
model and report the wrong UUID at `/version`. It pairs with
`assignment3/docker-compose.yml` — the only compose file among the three:

```yaml
services:
  mnist-api:
    ports: ["8005:8000"]
    environment:
      - PRED_MODEL_UUID=m-e8652fd264804ad8bdc71bca80f9757e
      - PRED_MODEL_PATH=/models/model.pt
    volumes:
      - ./conf:/app/conf:ro
      - ./logs:/app/logs
      - ./models:/models:ro
  streamlit:
    ports: ["8015:8501"]
    depends_on: [mnist-api]
```

Read-only mounts for `conf/` and `models/`, writable only for `logs/`,
two-service API+UI topology. This is the missing deployment layer. Steal the
required-settings + env-injection + ro-mount combination as a unit; it's a
coherent pattern, not three tricks.

**8.4 li_yang_chew: the best Dockerfile — steal this.**
`assignment3/Dockerfile`:

```dockerfile
RUN groupadd --system --gid 999 nonroot \
&& useradd --system --gid 999 --uid 999 --create-home nonroot
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project --no-dev --group backend
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --group backend
USER nonroot
```

BuildKit cache mounts, deps-then-source two-phase sync for layer caching,
`--locked --no-dev`, `UV_COMPILE_BYTECODE` for faster cold start, and an
actual non-root user. Compare the maintainer branch's `Containerfile`, which
has the non-root user **commented out**. dengfeng's is weakest of the three:
`uv sync --group dev --group training --group backend` pulls jupyterlab and
the full training stack into a serving image, and no lockfile is copied so
`--locked` can't be used.

**8.5 Regression to quarantine: peers stripped the maintainer's error
handling.** The maintainer's `process_data.py` is the one place where their
fill-in clearly beats both peers — explicit permission/existence checks that
raise with context, per-image `try/except` with counters, and a
reconciliation log:

```python
        logger.info(
            "Subdirectory processed: %s | Train images saved: %d/%d | Test images saved: %d/%d",
            curr_raw_data_subdir_path, train_images_saved, train_length,
            test_images_saved, test_length
        )
```

Saved-vs-expected counts make partial failures visible instead of silent.
Both peers' versions are bare `os.listdir` + `pd.read_csv` + unguarded
`save_image`. dengfeng additionally has a real bug — `shutil.copy` of
`test.csv` sits **inside the per-batch image loop**, recopying it once per
test image. Take the maintainer's version here.

Candidate for skeleton: **yes** — dengfeng's MLflow artifact-namespacing +
`input_example` + threaded init flag (8.2), dengfeng's
required-settings/compose/ro-mounts (8.3), li_yang's Dockerfile (8.4), the
maintainer's defensive `process_data.py` + counter reconciliation (8.5).
**No** to canon's kwarg filter, which 8.1 proves is a footgun.

## 9. Serving shape `[FILL-IN]`

`mnist_fastapi/` is `main.py` (app + CORS + router mount) / `config.py`
(`pydantic_settings.BaseSettings`, module-level `SETTINGS`) / `deps.py`
(module-level `PRED_MODEL, DEVICE`) / `v1/routers/model.py`. `UPPER_CASE`
module globals (`APP`, `ROUTER`, `SETTINGS`, `PRED_MODEL`) throughout —
unusual but consistent, and it's canon's convention (the `deps.py` scaffold
comment says "DO NOT MODIFY the constant name").

Versioned prefix from settings, `openapi_url` under it:

```python
API_V1_STR = mnist_fastapi.config.SETTINGS.API_V1_STR
APP = fastapi.FastAPI(title=..., openapi_url=f"{API_V1_STR}/openapi.json")
```

The maintainer adds `/healthz` and `/` (dengfeng keeps only `/healthz`, as
`async`), and wraps model loading in `@lru_cache(maxsize=1)` with a comment
reasoning that module-level execution already caches — belt-and-braces,
mildly over-engineered.

Two real problems in the maintainer's `v1/routers/model.py`, both inherited
from canon's hint code and both worth fixing rather than propagating. First,
uploads are written to **CWD under the client-supplied filename**
(`open(image_file.filename, "wb")`) — path traversal via `../` and a
collision risk under concurrency; then `os.remove(image_file.filename)` in
`finally`. Should be `tempfile` + a sanitized name, or decoded straight from
the in-memory bytes with no disk round-trip at all. Second,
`classify_multi` raises `HTTPException` on the first bad file, discarding
results for every file already processed — partial-success semantics would
serve callers better. The maintainer does improve on canon by returning
calibrated confidence (`torch.exp(output)` → percentage) and calling
`PRED_MODEL.eval()`, which dengfeng's version omits.

Candidate for skeleton: **partial** — keep the four-file split,
settings-driven versioned prefix, `/healthz`, and module-level model load.
Rewrite file handling (no client-named disk writes) and batch error
semantics before reuse.

## 10. Assignment 6 — what carried over `[FILL-IN]`

Carried: `@hydra.main`, `setup_logging` + `mlflow_init`/`mlflow_log`
(byte-identical to a3 `general_utils.py` **apart from CRLF line endings** —
the whole-file diff is an artifact, not a rewrite), the `if
mlflow_init_status: artifact_uri = mlflow.get_artifact_uri(); ...;
mlflow.end_run()` epilogue copied near-verbatim, JSON logging config.

Dropped or degraded:
- **Package structure gone.** a3 has `src/mnist/{data_prep,modeling}/`; a6
  is flat `src/*.py`. Imports are inconsistent in one file —
  `ml_experiment.py` mixes `from src.datapipeline import ...` (absolute)
  with `from .general_utils import ...` (relative), which cannot both
  resolve under a single invocation style.
- **`get_original_cwd()` dropped.** a6 uses bare relative paths under
  Hydra's chdir. Fragile exactly where a3 was careful.
- **`logging.basicConfig` at import time** in `datapipeline.py` and
  `ml_model.py`, fighting the `dictConfig` that `setup_logging` installs.
  a3 never does this.
- **Stray `print`** (`print(self.config)`, `print(X_test.shape)`) instead
  of logger calls.

New and genuinely useful: `mlflow_init` **inside** the per-horizon loop with
`end_run()` at the bottom, giving one MLflow run per forecast horizon —
correct shape for multi-horizon forecasting. `TimeSeriesSplit(n_splits=5)`
for CV plus a hard temporal cutoff (`train_val_cutoff = "2014-01-01"`) for
holdout. Artifacts-directory convention (`artifacts_dir`) collecting
`metrics_lag_{lag}.json`, `test_results_lag_{lag}.csv`,
`true_vs_pred_lag_{lag}.png`, `xgb_model_lag_{lag}.pkl`, all logged via
`log_artifact` — richer than a3. `joblib.dump` for sklearn/XGBoost instead
of `torch.save`. `Datapipeline` uses method-chained `.pipe(...)`
composition, which reads well.

`WindowGenerator` (a6 `windowing.py`) is the standard TF tutorial windowing
class — `lookback`/`lookahead`/`total_window_size`, slice-based input/label
indices, `tf.keras.utils.timeseries_dataset_from_array` +
`.map(split_window)`, `train`/`test` as properties. Note a6 pulls in
**TensorFlow** alongside a3's PyTorch (`ml_model.py` is XGBoost;
`cnn_model.py`/`rnn_model.py` are Keras) — three frameworks across two
assignments, so no single-framework assumption holds. `windowing.py` also
carries a junk auto-import, `from pyexpat import features`.

Candidate for skeleton: **partial** — steal run-per-horizon MLflow scoping,
the `artifacts_dir` convention, and TimeSeriesSplit-plus-temporal-cutoff.
Explicitly do **not** carry a6's flat layout, mixed imports, bare relative
paths, or `basicConfig` calls; a3's package structure is the better base.

## 11. Pass D skims

**assignment1** (earliest baseline) — pre-Hydra, pre-MLflow,
pre-logging-config. `src/{datapipeline,model,decision_tree,random_forest}.py`,
config passed as a `params: Dict[str, Any]` argument to `Model.train`,
`logging.basicConfig(level=logging.INFO)` at module scope, sklearn
`Pipeline`/`ColumnTransformer` inline in a module-level
`transform(data_path)` function. Grouped-import comment convention
(`# Standard library imports` / `# Related third-party imports` /
`# Local application/library specific imports`) appears here and survives
into a3 `process_data.py` — the one stylistic thread running the whole
corpus. Confirms the a3 conventions are course-supplied scaffolding, not
something the maintainer converged on independently.

**assignment10 `hands-on-project-diy-ver`** (structure only, out of scope) —
the most mature architecture in the repo and, unlike a3, plausibly all the
maintainer's own. `src/loaders/` (7 files) + `src/processors/` (6) +
`src/vectorstore/chroma_store.py` + `pipeline.py` orchestrator +
`api.py`/`frontend.py`. `loaders/base.py` defines an ABC plus a `@dataclass
ProcessedDocument(content, metadata, source, doc_type)` with `to_dict()`,
`__init__` validating existence eagerly (`raise FileNotFoundError`),
`@abstractmethod load() -> List[ProcessedDocument]`, and a shared
`_create_metadata(**kwargs)` helper seeding `source`/`filename`/`file_type`.
Parallel loader/processor hierarchies per modality, `DataPipeline` taking an
injected `Optional[ChromaDBStore]` with per-modality chunk-size params. Uses
`pathlib`, full type hints, Google-style docstrings — none of which the
a3/a6 code does. Flagged for the future LLM skeleton; the ABC +
dataclass-record + injected-store pattern is the reusable part.

## Addendum (2026-07-30): assignment5 `src/train.py` — the closest ancestor of the DL trainer

Found after the main pass (assignment5 was not in the trawl plan's file
list; surfaced by the maintainer's recollection of using an external early
stopping library). On `origin/qjjustin_leo`,
`assignment5/src/train.py::train_model` combines, in one function:

- `from early_stopping_pytorch import EarlyStopping` (pinned in
  `requirements.txt` as `early-stopping-pytorch`), wired as
  `EarlyStopping(patience=3, verbose=True, path=best_model_path,
  trace_func=logger.info)`. The library both tracks patience **and saves
  the best `state_dict` to `path` on every val-loss improvement** — early
  stopping and best-checkpoint persistence in one object, with logger
  integration.
- The canon MLflow wrappers (`mlflow_init`/`mlflow_log`/
  `mlflow_pytorch_call`), `step_offset` resume-aware epoch range.
- `torch.optim.lr_scheduler.StepLR`, Adam, config-driven
  `model_checkpoint_dir_path`, sample-weighted loss accumulation
  (`loss.item() * data.size(0)` / `len(dataset)`), tqdm-wrapped loops,
  `pin_memory`/`num_workers` cuda kwargs.

Gaps against the maintainer's stated preferences: train/validation loops
are inlined rather than factored into `run_one_epoch`/`evaluate` helpers,
and StepLR rather than a plateau scheduler. The target DL trainer is
therefore: this function + epoch-helper factoring + `ReduceLROnPlateau` +
`monitor: {name, mode}` checkpointing.

Candidate for skeleton: **yes** — adopt `early-stopping-pytorch` rather
than hand-rolling early stopping (decision: maintainer, 2026-07-30), and
use this file as the base of the DL training module.

## Open questions for synthesis

1. **Canon vs. merit.** §4's `co_varnames` filtering is canon *and*
   demonstrably harmful (§8.1). Do skeletons reproduce AISG conventions
   faithfully for familiarity, or fix them? Recommendation:
   fix-with-a-comment, but this is a policy call affecting several patterns.
2. **Which fill-ins carry authority at all?** Once the scaffold boundary is
   known, the maintainer's own "conventions" shrink to a handful of files,
   several with real bugs (hardcoded `mlflow_init_status=True`, client-named
   file writes). Should the skeleton follow the maintainer's branch, or take
   best-of-three per pattern as §8 suggests?
3. **Framework scope.** a3 PyTorch, a6 XGBoost + TensorFlow/Keras, a10
   LLM/Chroma. One framework-agnostic skeleton (config/logging/MLflow/
   artifacts) with pluggable model layers, or separate skeletons per stack?
4. **Config system.** Commit to Hydra everywhere and fold a6's
   `ts_params.yaml` into a config group, or sanction the plain
   `yaml.safe_load` escape hatch for domain configs? Affects whether sweeps
   can reach domain params.
5. **Compose/deploy layer.** dengfeng's compose is the only one; it's a toy
   but the right shape. Does the skeleton ship a compose file, and does it
   adopt the required-settings-no-defaults stance (fails fast, but breaks
   bare `uvicorn` local runs without a `.env`)?
6. **Unverified.** Nothing was executed — all findings are static reads.
   The `resume`/`step_offset` path in particular has version-guessing code
   that should be run against a pinned MLflow before trusting it. Also
   unexamined: `src/tests/` contents (only filenames seen),
   `mnist_streamlit/app.py` (both peers rewrote it substantially — possibly
   worth a look for the UI layer), and a6 `cnn_model.py`/`rnn_model.py`
   bodies.
7. **Line-ending hygiene.** a6 files are CRLF, a3 files LF, with no
   `.gitattributes` — cosmetic, but it made one file look wholly rewritten
   when it was byte-identical. Worth normalizing in any skeleton to keep
   future diffs honest.
