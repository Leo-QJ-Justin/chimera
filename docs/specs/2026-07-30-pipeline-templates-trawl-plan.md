# Pipeline Templates & Skeletons — Trawl Plan

> Task spec for chimera. Written 2026-07-30. Status: approved (maintainer, 2026-07-30).
> Purpose: mine the maintainer's project corpus for pipeline architecture and
> configured utilities, then codify them as ready-to-use skeletons (experiment
> tracking with MLflow, logging, model checkpointing and saving, config-driven
> pipelines). Siblings: the analysis-style mining reports in docs/research/
> (2026-07-30), which covered notebook prose style; this trawl covers **code
> structure and engineering practice**.

## Goal

Produce evidence-based inputs for:

1. **Pipeline skeletons** — templated repo/package layouts a new ML project can
   start from (likely two sizes: assessment-weight and production-weight).
2. **Configured utils** — drop-in modules for MLflow experiment tracking,
   logging setup, model persistence/checkpointing, config loading + validation,
   seeding/reproducibility.
3. **Skill/command updates** — whatever the loop needs so /design-project and
   /start-task can scaffold and use these (decided at synthesis, not before).

Per creating-skills, nothing ships without the gate: each candidate deliverable
gets a Create | Absorb | Automate | Drop verdict at synthesis.

## Resource inventory

| # | Resource | Location | Access |
|---|----------|----------|--------|
| 1 | Dynamic-simu-model (AIAP end-to-end project) | `~/dynamic-simu-model-aut0` | local, ready |
| 2 | Micron tech assessment | `~/dev/chimera/Micron_Tech_Assessment.zip` (extract to scratchpad, never commit) | local, ready |
| 3 | all-assignments (AIAP coursework) | `~/all-assignments`; branches `origin/qjjustin_leo` (maintainer), `origin/li_yang_chew`, `origin/dengfeng_zhou` | local, ready |
| 4 | Atlas (Obsidian vault of guides) | `/mnt/c/Users/leoqi/Desktop/Atlas` | readable from WSL |
| 5 | Work.pdf (Sembcorp work, images of code) | other machine | **pending transfer** |

Read-only throughout: nothing in these repos is modified; branch inspection via
`git ls-tree` / `git show origin/<branch>:<path>` so the checkout is never moved.

## Pass 1 — dynamic-simu-model (backbone candidate)

The most mature resource: four pipelines, each `classes/` (OO, base ABC) +
`modules/` (stateless) + `configs/` (YAML + pydantic schema) + `pipeline.py`.

Read, in order:

1. **Docs first** (they narrate intent): `docs/pipeline_execution_guide.md`,
   `docs/training_pipeline_mlflow_integration.md`, `docs/configuration.md`,
   `docs/training_pipeline.md`, `docs/data_pipeline.md`,
   `docs/inference_pipeline.md`, `docs/optimisation_pipeline.md`,
   `docs/unit_tests.md`.
2. **Utils** (the direct skeleton feed): `src/mlflow_utils.py`, `src/utils.py`,
   `src/schema.py`, `src/experiment_runner.py`,
   `src/pipelines/training_pipeline/modules/{model_persistence,artifact_utils,hyperparameter_tuning,evaluation,confidence_intervals,shap_utils,data_loading}.py`,
   `src/app/logger.py`.
3. **Architecture**: one full pipeline vertical (training) end to end —
   `pipeline.py`, `configs/training_pipeline.yaml`, `configs/schema.py`,
   `configs/optuna_search_ranges.yaml`, `classes/base_forecaster.py` + one
   concrete forecaster; then skim the other three pipelines for deltas.
4. **Run artifact discipline**: `outputs/training_pipeline/20260317_092455/`
   (timestamped run dir with config snapshot) and how `main.py` wires entry
   points.
5. **Experiment workflow**: `configs/custom/*.yaml` + one experiment notebook
   (`feature_elimination_experiment.ipynb`) to see how notebooks drive the
   config-based runner.
6. **Quality gates**: `.pre-commit-config.yaml`, `conftest.py`, one test suite
   (`tests/training_pipeline/`) for fixture and contract-test patterns.

Questions to answer: What does the MLflow integration actually log (params,
metrics, artifacts, model registry)? How are config, schema validation, and CLI
override layered? What is the checkpoint/save format and reload contract? What
is worth carrying into a skeleton vs what is project-specific?

## Pass 2 — all-assignments, assignment3 (canonical AISG conventions)

The shared MLOps scaffold all apprentices filled in: `conf/{logging,
train_model,process_data,batch_infer}.yaml`, entry scripts `src/{train_model,
process_data,batch_infer}.py`, `src/mnist/` package, FastAPI + Streamlit
serving, Docker, GitLab CI.

Per branch (`qjjustin_leo`, `li_yang_chew`, `dengfeng_zhou`), read:

- `conf/logging.yaml` + `src/mnist/general_utils.py` (the logging +
  seed + config-loading idioms — likely the origin of the house style)
- `src/train_model.py`, `src/process_data.py`, `src/batch_infer.py` (entry
  script shape, Hydra/argparse/env handling, MLflow calls)
- `src/mnist/modeling/utils.py` (checkpointing/saving in the torch context)
- `src/mlflow_test.py`, `.gitlab-ci.yml`, Dockerfiles; `docker-compose.yml`
  (dengfeng only)
- `pyproject.toml` for tooling config (lint, format, pytest)

Method: read the maintainer's branch fully; then diff the two peers against it
(`git diff origin/qjjustin_leo origin/li_yang_chew -- assignment3/src` etc.)
and record only meaningful divergences — better error handling, cleaner
structure, practices worth stealing. The three branches share the provided
skeleton, so raw file lists are identical; the signal is in the fill-in.

Also per branch, lighter passes:

- **assignment6** (time series): `src/{datapipeline,ml_experiment,windowing,
  ml_model,cnn_model,rnn_model}.py`, `conf/*.yaml` — the time series variant
  of the same conventions.
- **assignment1**: `src/datapipeline.py`, `tests/` — earliest-form baseline,
  skim only.
- **assignment10** (maintainer branch only): `hands-on-project-diy-ver/src/`
  loaders/processors/vectorstore base-class pattern — note for a future LLM
  skeleton, out of scope for this task's deliverables.

## Pass 3 — Micron assessment (assessment-weight variant)

Extract zip to scratchpad. Structure already mapped in the analysis-style
mining report; this pass reads the **code**: `src/pipelines/data_pipeline/
pipeline.py`, `training_pipeline/{pipeline.py,classes/base_classifier.py,
modules/{evaluation,resampling}.py}`, `main.py`, `pyproject.toml`.

Questions: what did the maintainer keep when forced to move fast (this defines
the assessment-weight skeleton's floor)? What did they drop relative to
dynamic-simu-model (no MLflow? no schema validation?) — and should the
skeleton restore any of it cheaply?

## Pass 4 — Atlas (the stated best practices)

Read as the cross-check: what the maintainer *says* is best practice, vs what
the code *does*. Divergences are discussion items, not silent resolutions.

- `00 Notes/Engineering & MLOps/Workflow & Reproducibility/`: `Logging with
  MLflow.md`, `Reproducibility.md`, `Pre-Commit Hooks.md`, `CI-CID Gitlab
  Configurations.md`, `Containerization with Docker.md`, `nbqa package for
  formatting and linting.md`, `Working with Virtual Environments...md`
- `00 Notes/ML Models/Deep Learning/Foundations/Neural Network Helper
  Functions.md` — 205-line torch harness (logging, device, train-one-epoch,
  evaluate, overfit-single-batch sanity check, predict, training loop,
  model/optim/loss setup). Direct seed for the deep learning training utils.
  Sibling: `Neural Networks — Architecture, Training & Optimisation.md`.
- `00 Notes/ML Methods & Workflow/Evaluation/`: `Cross-Validation.md`,
  `Hyperparameter Tuning.md`, `Model Evaluation.md`
- `00 Notes/Data Engineering/Data Pipelines & Formats/Data Engineering-End-to-
  end Pipelines.md`
- Skim `docs/superpowers/specs/` (two past project design specs) for how
  projects were scoped.

Out of scope here but noted for the deferred per-topic EDA playbooks task:
`Exploratory & Preparation/` notes (EDA for Images, EDA for NLP, etc.).

## Pass 5 — Work.pdf (blocked)

Pending transfer from the other machine. When it arrives: read for
Sembcorp-era practices not present in the AIAP corpus; fold into the same
research doc. Do not block synthesis on it — add an addendum if it lands late.

## Outputs and order of work

1. One research doc per pass under `docs/research/`:
   `2026-07-XX-pipeline-trawl-<resource>.md` — evidence with file paths,
   verbatim snippets of the idioms worth keeping, and an explicit "candidate
   for skeleton: yes/no/why" call per pattern. Same evidence-first style as
   the analysis-style mining reports.
2. **Synthesis discussion with the maintainer** (not unilateral): proposed
   skeleton inventory, per-util source-of-truth choice (e.g. whose logging
   setup wins), open divergences between Atlas and the code, and the gate
   verdicts. Decisions recorded with role and date.
3. Then a separate build task via /start-task: implement the skeletons +
   utils as chimera deliverables (form TBD at synthesis — likely
   `templates/` additions plus a skill; possibly a scaffold step in
   /design-project).

## Constraints

- Read-only on all source repos; assessment zips never enter git history
  (`*.zip` is gitignored; extraction goes to the session scratchpad).
- All chimera-side outputs are user agnostic: role terms and dates, no
  personal names outside literal git refs and paths that are themselves data.
- Skeleton code follows the house conventions already codified: Google-style
  docstrings, logging in src / print in notebooks, `random_state=42` threaded
  as a single seed parameter, leakage-as-architecture (stateless clean
  pre-split, stateful fit/transform train-only).
