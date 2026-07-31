# Project Skeletons

Ready-to-use project scaffolds.
Design provenance: `docs/specs/2026-07-30-pipeline-skeletons-design.md`
(decisions D1-D13 and revision R1; evidence in
`docs/research/2026-07-30-pipeline-trawl-*`).

## Inventory

| Scaffold | Path | When |
|----------|------|------|
| ML Pipelines | `ml-pipelines/` | Any ML/data project: four config-driven pipelines (data, training, inference, evaluation) with pluggable trainers. Self-contained — ships its own `core/` utils package and tests |
| AI Application | *(future task)* | Product/app projects; will pair with the ML scaffold for hybrid projects |

## The ML Pipelines scaffold in one paragraph

Four pipelines, each with `classes/` (stateful objects behind an ABC),
`modules/` (stateless functions), and a thin `pipeline.py` orchestrator;
Hydra configs at the repo root with pydantic validation on top; MLflow
tracking on by default (sqlite backend) with a JSONL metrics sidecar;
run artifacts under `outputs/<pipeline>/<timestamp>/` with
latest/best pointers, config snapshots, and recorded split membership.
Model families plug in as **trainers** (`sklearn`, `lightgbm`, `torch`)
behind one `BaseTrainer` contract selected by the Hydra `model` group —
the training pipeline just builds the configured trainer and fits.

## The contracts every pipeline honours

**Data/training boundary (D5).** The data pipeline runs load → stateless
clean → stateless features and outputs the **full** processed table plus
split-enabling keys. It never splits and never fits: *if it needs
`.fit()`, it is not data-pipeline code.* The training pipeline owns the
split, all fitted preprocessing, and the model. Frozen holdouts are
declared boundaries (dates/ID lists), never physically split data.

**One data path (D4).** Training, evaluation, and serving all consume the
same sample-building path; evaluation consumes the inference pipeline's
predictions. If inference re-implements any preprocessing, that is a bug
by definition.

**Split reproducibility (D8).** Split **membership** is persisted with
stable keys and fingerprints (`core/splits.py`) — seed + protocol is the
generator, the artifact is the record.

## Evaluation protocol decision table (D9)

| Data regime | Split | Model comparison | Final fit |
|---|---|---|---|
| i.i.d. tabular, ample data | stratified shuffle + untouched test | k-fold CV on train (fresh pipeline per fold) | fit on train+val, report test once |
| i.i.d. tabular, small data | stratified shuffle | nested CV (inner tune, outer estimate) | choose per project: refit-on-all vs holdout — record the choice in the decision table |
| Time series | temporal boundary, test touched once | expanding-window walk-forward | fit through the val boundary; never train on test period |
| Grouped/hierarchical (entities repeat) | group-aware split on entity keys | GroupKFold | fit on train groups |

## Scaffolding a project (what /design-project Phase 5 does)

1. Copy `ml-pipelines/` into the new repo root — it is self-contained
   (its `src/PROJECT/core/` utils and tests ship with it).
2. Rename `src/PROJECT/` to `src/<package_name>/`. Relative imports mean
   no code edits are needed; the remaining rename touchpoints are listed
   in the scaffold's README.
3. Set `[project] name` in `pyproject.toml`; `uv sync`.
4. `pre-commit install && pre-commit install --hook-type pre-push`
   (adapt the env prefix in the pre-push hooks).
5. Delete the example/placeholder cleaning steps as real ones land —
   they are marked in the code.

## Conventions carried by the scaffold

- `logger = logging.getLogger(__name__)` per module; logging configured
  once at the entry point; scalars via logger, pre-formatted blocks via
  `print`.
- One seed source (`seed` config key) threaded explicitly; seed persisted
  into run metadata.
- Google-style docstrings; comments state the reason, not the action.
- Generated artifacts (`data/processed/`, `outputs/`, `logs/`,
  `mlflow.db`) are gitignored and disposable.
