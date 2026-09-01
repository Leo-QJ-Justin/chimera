# Changelog

All notable changes to chimera are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [SemVer](https://semver.org/).

## [1.9.0] - 2026-09-01

Thirteen changes from the first full-project retrospective (a pipeline
project run entirely under chimera), plus the three adoptions the parent
repos (Superpowers, BMAD, ECC) still owed. Spec:
`docs/specs/2026-09-01-v2-improvements.md`. The organizing principle: an
evidence phase closes with binding constraints — evidence → constraint →
implications — never with findings or verdicts alone.

### Added
- `skills/writing-comparative-reports` — the report contract and the
  profile-to-brief recipe for any many-instance investigation (corpus
  profiling, tool comparison, log analysis); routed from using-chimera.
- `agents/corpus-profiler.md` — mechanical corpus profiling per that
  contract, the non-tabular sibling of `eda-profiler` (which gains only
  a dispatch note).
- `skills/persistent-model-discovery` — six questions locking grain,
  immutability, corrections, and consumers into an approved
  `docs/technical-requirements.md` when its trigger fires; one PRD line
  and no file otherwise.
- `commands/retrospect.md` — the learning loop formalized: friction
  events → quality gate (observed, reusable, overlap grep, form check)
  → verdicts → improvement spec in the consuming project. Invoked,
  never hooked.
- `docs/process-map.md` — the living process map, auto-loaded via
  CLAUDE.md and updated in the same commit as any flow change.
- `docs/testing/pressure-scenarios/` — one scenario per change, derived
  from its observed failure: setup, failure to reproduce, pass
  condition, two stacked pressures, failure-form mapping. Every skill
  edit walks its scenarios before landing.

### Changed
- `/design-project`: Phase 1 splits into DISCOVER → 1a DATA-CONTACT
  SPIKE (PRD gated on profiling when a real corpus exists) → 1b BIND
  (evidence converted into approved commitments) → 1c PRD; Phase 2
  records the Tier-1 ADR pointing at the TRD; reference-integrity lines
  added to the 1b/1c/2/3 self-checks.
- `designing-tasks`: build-mode specs carry a Decisions section and a
  flow sketch checked against the depth budget (two files per traced
  call when the project defines none); FR contents are re-presented for
  item-level re-confirmation; correctness-path heuristics and scope
  renegotiations are asked as explicit questions, never only recorded.
- `writing-plans` + `finishing-a-branch`: plans carry a `## Deviations`
  section appended at the moment a departure is made; the list is
  briefed to the code-reviewer as questions to judge.
- `finishing-a-branch`: Amendment path for post-merge scope corrections
  (tests and every doc stating the amended behavior move in the same
  commit), routed from using-chimera.
- `exploring-reproducibly` + `code-reviewer`: every adopt decision
  closes with `Constraint:` and `Implications:` lines, or an explicit
  "no design consequence".
- `writing-in-ste`: notation gets a plain-word reading at first use
  (rule row + process step).
- Templates: both PRDs gain a required "Commitments realized" section;
  system design gains the TRD preamble line.
- `docs/research/2026-08-03-prd-trawl-bmad.md` §7: the
  "length scales with stakes" rejection qualified — the TRD trigger
  scales scope (whether an artifact applies), never rigor.

## [1.8.1] - 2026-08-10

Corrects the partitioning shipped hours earlier in 1.8.0. No capability
is added or removed; the same material now lives in one artifact instead
of two. Reasoning:
`docs/research/2026-08-10-ai-architecture-trawl.md` §5.

### Changed
- `templates/architecture-ai.md` is **removed**. Its content folds into
  `templates/system-design.md`, which gains a `Boundary` column on the
  module table (deterministic or probabilistic, with the output contract
  named for anything probabilistic), an **External interfaces** table
  beside the internal module contracts, and an **AI properties** section
  — memory in four layers, evaluation in three, cost with its arithmetic
  — deleted for projects with no model component.
- The model, embedding, retrieval-store, and framework choices are Phase
  2 ADR topics named in `/design-project`, not template sections. They
  were recording a decision, its reasoning, and its rejected alternative
  beside the ADR that already held all three.

Why: memory, evaluation, and cost are whole-system properties, the same
kind of thing as the risk table already in system design. The remaining
sections each had a home already — ADRs for the technology choices, the
module table for the boundary and the interfaces. Two architecture
artifacts now: ADRs answer why this and not that, system design answers
what the system is.

## [1.8.0] - 2026-08-10

Trawl of `sagarika29/ai-system-architect` (MIT). Verdicts and the two
rejected devices: `docs/research/2026-08-10-ai-architecture-trawl.md`.

### Added
- `templates/architecture-ai.md` — the decisions an LLM, embedding, or
  retrieval component forces: the deterministic-versus-probabilistic
  boundary, then model, embeddings, retrieval store, framework,
  interfaces, memory in four layers, deployment, evaluation in three
  layers, and cost with visible arithmetic. Filled at `/design-project`
  Phase 2 whenever the system has such a component — a condition, not a
  project type, so an application and an ML/data project can both use it.
  "None" is a recorded decision; a blank section is a gap. The template
  names which decisions must exist; the ADRs hold their reasoning.
- Risk register in `templates/system-design.md`: risk, likelihood,
  impact, mitigation, and **detection signal**, ranked by expected cost,
  with at least one non-technical row. A mitigation with no detection
  signal is a hope, and where a roadmap gate row checks the risk, the
  signal names that row.
- Confidence field on every ADR — `[High]`, `[Moderate — depends on X]`,
  `[Low — verify before committing]` — and a Phase 2 self-check that
  fails uniform confidence: if every tag reads High, the tradeoffs were
  not examined.

### Changed
- Every deferral — debt-register entry, deferred roadmap item, future
  improvement — is now written as **trigger condition → change →
  unlock**. A deferral with no trigger never gets revisited, because
  nothing says when to look.

### Deferred
- **AI Application scaffold / LLM-RAG skeleton** — trigger: a second
  project needs the same retrieval-and-serving shape → change: extract
  the skeleton from the first one that ships → unlock: `/design-project`
  Phase 5 scaffolds AI applications the way it already scaffolds ML
  pipelines. `templates/architecture-ai.md` is the contract such a
  skeleton must satisfy.
- **Count and geospatial EDA playbooks** — trigger: reference material
  with real technique for either topic lands → change: draft from it in
  the established playbook form → unlock: full topic coverage in
  `exploring-reproducibly`.
- **Mechanical genesis-doc validator** — trigger: a filled PRD reaches
  an approval gate with a missing section or a broken FR reference →
  change: a script in `tests/` that greps for required sections, FR IDs
  with Done-when lines, and assumption-index round-trip, failing closed →
  unlock: the prose self-checks stop being the only guard.

## [1.7.0] - 2026-08-09

Seven amendments distilled from a field run of 1.6.0 — a `/design-project`
pass over an existing document corpus. Provenance and the one deviation
that was declined:
`docs/research/2026-08-09-genesis-amendments-from-field-use.md`.

### Added
- `writing-in-ste` skill — Simplified Technical English as the register
  for genesis documents and any text an agent must parse without a human
  to resolve ambiguity. Ported (not referenced) from
  `danyuchn/asd-ste100-skill`, MIT, which repurposes ASD-STE100 Issue 9;
  the standard's approved-word dictionary is not reproduced. Wired into
  the `using-chimera` routing table and every `/design-project` phase
  gate, with the rewrite pass running before approval, never after.
- `## Terms` table in both PRD templates — one row per term that is not
  common English, one meaning each. This reverses the Glossary rejection
  recorded in the BMAD trawl: STE's one-word-one-meaning rule needs an
  anchor, and without one domain nouns drifted between documents in the
  field run.
- `### Issue schedule` in `templates/prd-ml.md` — the eight properties
  that specify a forecast (issue frequency, issue time, as-of cutoff,
  target set, resolution, lead-time range, output shape, re-issue
  policy), the fixed-event-versus-rolling shape, and a worked example
  with concrete timestamps. The as-of cutoff is the leakage contract; a
  system that leaves it unstated cannot be audited for leakage.
- **Distill mode** for `/design-project` — offered at Phase 0 when an
  authoritative corpus already exists. Distilled PRDs open with a
  precedence header naming the source documents in order. Approval gates
  are unchanged: distillation changes the input, not the discipline.
- **Gate rows** in the roadmap — exploration rows realizing `-`, whose
  deliverable is a written go/no-go note, placed after the rows they
  gate, under the header rule "a slipped gate beats a false-green gate".
  Plus critical-path and parallel-rows footer notes.

### Changed
- ADRs carry three more fields: a status vocabulary that keeps live
  disagreement visible (`proposed`, `accepted, under challenge`), a tier
  label tied to reversal cost that doubles as the build-order argument,
  and a reversal-cost line in Consequences. Small reversible technology
  choices consolidate into one table ADR; deliberate shortcuts go in a
  debt-register ADR with expiry dates reviewed at each gate row.
- `templates/system-design.md` data flow is a mermaid `flowchart`
  (schedules a `gantt`); ASCII arrows are kept only for a single linear
  chain, and repo layout stays a text tree.

## [1.6.0] - 2026-08-03

### Added
- Requirements in the PRD templates: globally numbered `FR-N` blocks,
  each carrying at least one testable `Done when` line. They are the
  first thing in the genesis chain a task can be verified against —
  previously a requirement was restated in new words at every hop from
  PRD prose to verification checklist.
- Inline `[ASSUMPTION: ...]` tags with an index in both PRD templates, a
  guard metric beside every success measure, and an open-questions
  section at PRD altitude.
- `templates/prd-ml.md` gains a Prediction target section (unit of
  analysis, label definition, prediction window, exclusions, known
  prevalence) and states that the promotion threshold is set by the first
  exploration task, not at genesis — model quality never becomes an FR.
- Four-point PRD self-check (substance, done-ness, scope honesty, ID
  integrity) before `/design-project`'s Phase 1 approval gate, matching
  the self-review steps `designing-tasks` and `writing-plans` carry.
- `docs/research/2026-08-03-prd-trawl-bmad.md` — trawl of BMAD-METHOD
  (BMad Code, LLC, MIT), whose PRD template chimera's was originally
  modelled on, with adopt/reject verdicts per device.

### Changed
- `docs/roadmap.md` tables gain a `Realizes` column carrying the
  requirement IDs a row delivers. Task specs name the `FR-N` they realize
  and inherit its `Done when` lines as acceptance criteria;
  `verifying-before-done` builds its requirements checklist from those
  lines; `/start-task` Phase 6 amends the PRD when a task renegotiated a
  requirement. Every touchpoint is conditional on `docs/prd.md` existing,
  so loop runs in repos without genesis docs are unaffected, and
  exploration rows realize no requirements — they inherit the metric,
  baseline, and guard metric instead.

## [1.5.0] - 2026-08-03

### Added
- Zero-storage provenance in the ML Pipelines scaffold: chunked-sha256
  content fingerprint of the processed table recorded per run and checked
  at evaluation, `load_split_frames` replay of any run's exact split
  frames from roots and recipes, seeded Optuna samplers in every family
  tuner, and an `environment.json` package record per run.
- Scaffold technical documentation: `docs/pipelines.md` (per-pipeline
  reference) and `docs/extending.md` (nine recipes covering where a new
  metric, plot, trainer family, or pipeline stage goes).
- Coding-style rules pack (`rules/common/`, `rules/python/`), distributed
  by copy into `.claude/rules/chimera/` via `/new-project` and auto-loaded
  through CLAUDE.md imports; the code-reviewer agent treats rules
  violations as reportable findings. Chimera's own root CLAUDE.md imports
  the pack it ships.
- Per-topic EDA playbooks in `skills/exploring-reproducibly/`: a generic
  spine and a statistical-test appendix shared by four topic playbooks
  (tabular, time series, text, images), wired into `SKILL.md` alongside
  `analysis-style.md`. Externally sourced techniques carry an
  `[external]` marker until exercised in a shipped analysis; count and
  geospatial playbooks remain deferred pending reference material.
- EDA trawl research corpus under `docs/research/` (four documents:
  stated practice, practiced technique across four coursework branches,
  external curriculum cross-check, and the topic coverage map with
  recorded scope decisions).

### Changed
- Scaffold docstrings and comments rewritten in a professional library
  voice: Google-style docstrings throughout, no design-doc or planning
  references, comments state reasons at decision points. Verified
  comment-only via docstring-stripped AST equivalence.
- Scaffold abstraction cleanup: single environment record, shared
  `read_table` reader, trainer-registry if-chain inlined, dead code
  removed. Scaffold test count: 319.

## [1.4.0] - 2026-08-01

### Added
- Per-family tuning/evaluation protocol in the ML Pipelines scaffold,
  keyed on each trainer's own `uses_val_in_fit` declaration (R1.10):
  families whose fit never reads a validation split (`logreg`,
  `random_forest`) tune and fit on train+val pooled and select on an
  honest k-fold CV estimate (`cv_<metric>` in `best.json`); early-stopping
  families (`lightgbm`, `xgboost`, `torch`) keep the standing-val
  protocol.
- Procedure-level cross-validation (R1.11): `cross_validate` runs each
  family's whole training procedure per fold — fresh trainer, per-fold
  early-stopping carve (chronological tail under temporal mode) — and
  `selection.basis: cv` puts every family on the same CV yardstick so
  different families rank against each other in one output directory
  without touching test.
- Declarative, config-overridable search spaces (R1.12): each family
  declares `TUNABLE` (name → default range) in its own class body;
  `trainer.tune.space` narrows any range or drops a name with `false`;
  `tune.metric` is a project metric alias and a null `tune.direction` is
  inferred per metric, so an error metric cannot be silently maximised.

### Changed
- Trainer families are self-contained (R1.12): `sklearn_common.py` is
  dissolved and every family is one hop from `BaseTrainer`, declaring its
  full ML surface — `train`, `predict`, `predict_proba`, `evaluate`,
  `hyperparameter_tune`, `save`, `load`, `log_model` — in its own class
  body, enforced by `__dict__` contract tests. There is no shared Optuna
  sweeper: each family's tuner scores trials by the procedure it ships
  (pooled families via procedure CV, standing-val families on a carved
  20% holdout), in project metric aliases.
- The training pipeline is a pure orchestrator (R1.13): protocol knowledge
  moved into three per-family methods (`fit_frames`, `evaluate_run`,
  `selection_key`) and `pipeline.py` no longer reads `uses_val_in_fit`.
  Trainers stay tracker-free and receive plain values, never config
  objects.
- Booster tuning trials now early-stop against their carved holdout
  instead of training the full `n_estimators`, so tuned winners differ
  from historical runs; the `selection_cv` stage timer became `evaluate`
  (`time_evaluate_s`). Scaffold test count: 309.

## [1.3.0] - 2026-07-31

### Added
- `skeletons/ml-pipelines/` — self-contained ML Pipelines scaffold: four
  config-driven pipelines (data, training, inference, evaluation), each
  with `classes/`, `modules/`, and its own Hydra `configs/` directory,
  over an in-tree `core/` utils package (MLflow tracking with explicit
  run IDs and a JSONL metrics sidecar, run artifacts with latest/best
  pointers, split-membership persistence, seeding, logging, timing,
  pydantic config). Per-family trainers (`logreg`, `random_forest`,
  `lightgbm`, `xgboost`, `torch`) behind one `BaseTrainer` contract with
  per-family Optuna spaces and Hydra `trainer` config group; curated
  MLflow flavor model logging (no autolog); leakage-as-architecture
  boundaries (data pipeline never splits or fits; training owns split,
  fitted preprocessing, model; evaluation consumes the inference
  pipeline's predictions). 241 tests ship with the scaffold.
- Diagnostic artifacts, split by what they need: model-based figures
  (training curves from per-iteration history including booster eval
  curves, feature importances/coefficients, config-gated SHAP) draw
  post-fit in the training pipeline; prediction-based figures (confusion
  matrix, ROC/PR/calibration, residuals) draw in the evaluation pipeline
  and embed in `report.md`. Everything mirrors to MLflow via the
  whole-run-dir upload; `shap` is the optional `explain` extra.
- `skeletons/README.md` — scaffold inventory, pipeline contracts,
  evaluation protocol decision table, scaffolding steps.
- Design provenance: `docs/specs/2026-07-30-pipeline-skeletons-design.md`
  (D1–D13 + revisions R1.1–R1.9) and five evidence trawl reports under
  `docs/research/`.

### Changed
- `/design-project` Phase 5 now scaffolds ML/data and hybrid projects
  from `skeletons/ml-pipelines/` (copy → rename `src/PROJECT/` → set
  pyproject name).

### Deferred
- AI Application scaffold (second skeleton type, R1.1).

## [1.2.1] - 2026-07-30

### Changed
- User-agnostic sweep: all operational surfaces (skills, agents, commands,
  templates) and design docs now speak in role terms (the analyst, the
  maintainer, your human partner) with no personal names or references to
  past conversations. Author metadata in the plugin manifests is the only
  remaining personal reference. Regression guards added: a user-agnostic
  rule in `creating-skills` and a grep check in the smoke matrix.

## [1.2.0] - 2026-07-30

### Added
- `skills/exploring-reproducibly/analysis-style.md` — the analysis
  style contract (dash as structure never prose, de-hyphenated compounds,
  Observations & Findings cell format, decision tables before code,
  mandatory limitations close, chart conventions). Mined from the Micron
  and Mindef assessment corpora (see docs/research/).
- `eda-profiler` agent — mechanical first-pass dataset profiling (shape,
  info, missing/cardinality frame, duplicate checks, robust describe
  screens, target distribution), returning a draft in the style contract
  with judgment calls flagged as questions, never decided. Wired into
  exploring-reproducibly as an offer after Pin Everything.

### Deferred
- Per-topic EDA playbooks (tabular, count, time series, geospatial,
  text) — awaiting additional reference material before drafting.

## [1.1.0] - 2026-07-30

### Added
- `creating-skills` skill — skill authoring synthesized from Anthropic's
  skill-creator, Superpowers' writing-skills, and ECC's learn-eval gate:
  should-this-exist verdict (Create/Absorb/Automate/Drop), format rules,
  match-the-form-to-the-failure doctrine, and a test-before-deploy gate.
  Makes chimera self-sufficient for skill authoring; the external
  skill-creator plugin can be disabled. Routed from the bootstrap
  ("Creating or editing a skill").

## [1.0.0] - 2026-07-29

Initial release. A self-contained personal harness built per the
[v1.0 design spec](docs/specs/2026-07-29-chimera-v1-design.md): 8 skills,
3 commands, 1 agent, 2 hooks, 5 templates.

### Added
- **Skills** — `using-chimera` (bootstrap/router, injected every session),
  `designing-tasks`, `writing-plans`, `test-driven-development`,
  `exploring-reproducibly`, `verifying-before-done`,
  `debugging-systematically`, `finishing-a-branch`. Seven adapted from
  Superpowers (Jesse Vincent, MIT) with mode-awareness added;
  `exploring-reproducibly` written from scratch (pinned data, seeds,
  findings log, stopping rules, promotion rule).
- **Mode system** — every task declares build | exploration at kickoff;
  every loop stage has mode-specific behavior.
- **`/start-task`** — the loop: gate → mode → design → plan → execute →
  verify → finish (review gate inside), with a 3-attempt circuit breaker
  and plan-file resume.
- **`/design-project`** — project genesis: PRD (app-shaped, or ML-shaped
  via CRISP-DM phases 1-2), architecture ADRs, system design (module I/O
  contracts), roadmap backlog.
- **`/new-project`** — thin scaffolding (CLAUDE.md from template,
  gitignore, docs skeleton); never overwrites without a diff + approval.
- **`code-reviewer` agent** (read-only tools) — confidence gates,
  pre-report proof requirements, "zero findings is a valid review",
  false-positive skip list (adapted from Everything Claude Code, affaan-m,
  MIT), plus build and exploration (methodology) rubrics.
- **Hooks** — SessionStart bootstrap injection on `startup|clear|compact`;
  warn-only branch nudge on source edits on main/master (never blocks;
  resolves the edited file's git context; `CHIMERA_SILENCE_NUDGE=1` mutes).
- **Templates** — `CLAUDE.user.md`, `CLAUDE.project.md`, `prd-app.md`,
  `prd-ml.md`, `system-design.md`.
- **Tests & docs** — hook test scripts under `tests/`;
  `docs/update-procedure.md` (three-layer plugin update path);
  `docs/testing/smoke.md` (manual end-to-end matrix).
