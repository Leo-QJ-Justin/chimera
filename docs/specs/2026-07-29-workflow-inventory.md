# Chimera v1.0 — Bare-Minimum Workflow Inventory (Phase 0)

Status: LOCKED 2026-07-29. Phase 1 (reference mining) may remove or refine
items, never add scope.

Purpose: enumerate the workflows the harness must serve. Every skill, command,
hook, or CLAUDE.md line in v1.0 must trace back to one of these.

Selection principle — least machinery: for each workflow, escalate only as far
as needed: `CLAUDE.md line < skill < command < hook`. Hooks are reserved for
hard enforcement where instructions alone have failed.

---

## Architecture of the loop: two orthogonal axes

**Altitude.** Two altitudes, both in scope (revised 2026-07-29 — Leo's
workflow walkthrough evidenced project genesis as a repeated workflow, so
the original "conversational only, defer to v1.x" position is retired).
**Genesis** (`/design-project`, W10): brainstorm → PRD (app- or ML/CRISP-DM-
shaped) → architecture + tradeoffs (ADR) → system design (modules with I/O
contracts) → roadmap (task backlog with modes). **Loop** (`/start-task`,
W1–W8): executes one roadmap task at a time. The loop consumes genesis
artifacts as context and never re-litigates architecture; genesis never
writes implementation code. Decision rule between them: *empirically
settleable → loop (exploration task); infrastructure-rewriting to change →
genesis.*

**Mode.** Declared per feature at W1 with one question:
**"Is this feature producing code we'll keep, or an answer we'll act on?"**

- **Build mode** — deliverable is durable code: app features, libraries, data
  pipelines, feature-engineering modules, rerunnable training scripts, APIs.
  Strict TDD.
- **Exploration mode** — deliverable is knowledge: EDA, model experiments,
  backtests, hypothesis tests (quant projects); technical spikes (app
  projects). Reproducibility discipline instead of TDD.

Each project CLAUDE.md declares a **default mode**; each feature confirms or
overrides at kickoff. Every loop stage (W2–W7) has a short mode-specific
variant — one loop, two vocabularies, not two harnesses.

**Promotion rule (the bridge).** When an exploration result wins and must live
on, promoting it is a **new build-mode feature**. Experiment/spike code is
reference material, never the implementation. The pipeline version is written
test-first, with the experiment's numbers on the pinned data snapshot as
acceptance criteria. Spike code is not merged.

**TDD boundary.** Even in build mode, TDD covers the deterministic parts of ML
code (transforms, shapes, schemas, leakage checks). Model quality is
evaluation metrics — exploration-mode findings — not unit tests.

---

## Core loop (KEEP)

### W1. Start a feature
- **Failure mode:** starting *feature work* on `main` absentmindedly; vague
  scope; mode never chosen.
- **Mechanism:** command (`/start-task`) with a Phase 0 branch gate, plus
  a warn-only PreToolUse nudge on source edits on main (never blocks).
  Kickoff asks the mode question. Worktree option folded in here.
- **Enforcement note:** no ambient blocking — a hook that blocks legitimate
  direct-on-main work (docs, chores) is more enforcement than wanted. Hard
  gates are loop-scoped; the hook only nudges. See design spec §3.2.

### W2. Design before build
- **Build:** feature-level spec — behavior, interfaces, edge cases.
- **Exploration:** research brief — question, hypothesis, data, method, and
  *what result would change what decision* (prevents the aimless notebook).
- **Mechanism:** skill (adapted brainstorming, slimmed to feature scope).

### W3. Written plan before implementation
- **Build:** implementation plan — ordered steps, each with tests.
- **Exploration:** experiment plan — data prep, baseline, experiments,
  evaluation metric, and a **stopping rule** (prevents endless fishing).
- **Mechanism:** skill + file convention; plan files gitignored (`plans/`).

### W4. Implement
- **Build:** strict TDD, RED phase non-negotiable (the article's key finding:
  enforcement, not suggestion, changed output quality).
- **Exploration:** pinned data snapshot, fixed seeds, assumptions stated,
  findings logged as they emerge.
- **Mechanism:** skill (TDD adapted from superpowers) + mode flag.

### W5. Verify before claiming done
- **Build:** tests pass, thing actually runs — evidence before assertions.
- **Exploration:** results reproduce on a clean rerun; reported numbers match
  actual output.
- **Mechanism:** skill (verification-before-completion, near-verbatim).

### W6. Review before merge
- **Build:** one code-review pass on the diff. No Stop-hook gate — an
  automatic re-review would duplicate the single review pass for no signal.
- **Exploration:** methodology sanity pass — leakage, look-ahead bias,
  train/test hygiene; reviews the reasoning, not code style.
- **Mechanism:** step inside finish flow invoking one review subagent.

### W7. Finish a branch
- **Build:** merge/PR per preferences (no boilerplate footers), changelog,
  branch cleanup.
- **Exploration:** findings + decision recorded in the findings doc; the
  recorded decision *is* the product. Experiment code archived, not merged.
- **Mechanism:** skill (adapted finishing-a-development-branch), last
  /start-task step.

## Situational (KEEP)

### W8. Systematic debugging
- Loads only when a bug appears; near-zero standing cost.
- **Mechanism:** skill (adapted from superpowers).

## Bootstrap (KEEP — added in Phase 0 review)

### W9. New-project bootstrap
- **Mechanism:** thin `/new-project` command — copies the project CLAUDE.md
  template, sets up `.gitignore` (incl. `plans/`), git init conventions,
  prompts for one-paragraph brief + default mode. Scaffolds a home for
  project docs; does NOT generate PRDs or make design decisions.

## Genesis (KEEP — added 2026-07-29 on workflow-walkthrough evidence)

### W10. Design a project
- **Failure modes:** greenfield ML/AI ideas built without a PRD; architecture
  chosen without tradeoff discussion; no system design (modules + I/O) — the
  gap Leo identified in his own pre-chimera workflow; modeling choices
  settled by argument instead of experiment.
- **Mechanism:** command (`/design-project`, 5 phases, type-aware:
  application | ML/CRISP-DM | hybrid) + templates (prd-app, prd-ml,
  system-design). Produces the roadmap the loop consumes. See design spec
  §5.1.

### W12. Create or edit a skill (added 2026-07-30, shipped in v1.1)
- **Failure modes:** enthusiasm-driven skill sprawl (the 281-skill
  cautionary tale); process-summarizing descriptions; skills deployed that
  no agent ever failed without.
- **Mechanism:** skill (`creating-skills`) — gate verdict
  (Create/Absorb/Automate/Drop), format rules, match-the-form-to-the-
  failure, test-before-deploy. Replaces the external skill-creator plugin.

## Deferred to v1.x (named, not built)

- **W11. Capture learnings** — ECC-style `/learn` retro; first v1.x candidate
  once dogfooding produces friction data.

## Decided OUT of scope

- **Backlog CLI tooling (e.g. beads/`bd`)** — CUT (Leo, 2026-07-29). Plan files carry
  multi-session state; reintroduce only with dogfooding evidence.
- **Project resume** — covered by claude-mem + plan files + project CLAUDE.md.
- **Cross-session memory** — claude-mem's job.
- **Parallel agent dispatch / subagent orchestration** — native Agent tool.
- **Language rules (ECC `rules/`)** — v2 candidate, Python-first if ever.

## Cross-cutting artifacts

- **`templates/CLAUDE.user.md`** — durable global preferences, rebuilt
  deliberately from the live file (conventional commits, no co-author or
  boilerplate footers, subagents never commit, plans/ gitignored, context7
  for docs, frontend skill pairing).
- **`templates/CLAUDE.project.md`** — per-project template: what this is /
  architecture (+ links to PRD/design docs), run/test/build commands,
  conventions, gotchas, **default mode declaration**. Short — it loads every
  session.
