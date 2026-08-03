---
description: Design a new project - PRD, architecture, system design, and roadmap - before any code exists
argument-hint: "[one-line project idea | blank]"
---

# /design-project

**Input**: $ARGUMENTS

Project genesis: the altitude above the loop. Produces the documents
`/start-task` consumes. Ask questions one at a time; get approval at each
gate. All genesis artifacts are committed.

**The genesis-vs-loop decision rule (apply throughout):**

> If an experiment could settle it, don't settle it by argument — record it
> as a constraint and send the choice into the loop as an exploration task.
> If changing it later means rewriting infrastructure, settle it at genesis.

Model-family selection is the canonical loop-side decision; pipeline
orchestration is the canonical genesis-side one.

## Phase 0 — TYPE

Ask two questions (one message each):
1. Project type: **application** | **ML/data** | **hybrid**?
2. Does a repo already exist for this? (If yes, Phase 5 just commits docs.)

## Phase 1 — DISCOVER

Brainstorm the idea conversationally — the problem, who it's for, what
success looks like. One question at a time; propose options with a
recommendation where useful. Then fill the type-matched PRD template into
`docs/prd.md`:

- Application → `${CLAUDE_PLUGIN_ROOT}/templates/prd-app.md`
- ML/data → `${CLAUDE_PLUGIN_ROOT}/templates/prd-ml.md` (CRISP-DM phases
  1-2: business understanding, data understanding, constraints)
- Hybrid → both templates' sections, merged (product shell + ML core)

**Self-check before presenting** — fix inline, no re-review:

1. **Substance** — cut any section that drives no decision.
2. **Done-ness** — every FR carries at least one testable *Done when*;
   no unmeasurable adjective survives ("gracefully", "reasonable",
   "user-friendly").
3. **Scope honesty** — every inference tagged `[ASSUMPTION]` and listed
   in the index; every omission stated in Non-goals rather than left for
   the reader to infer.
4. **ID integrity** — FR IDs unique and contiguous.

**Approval gate:** your human partner approves `docs/prd.md` before
Phase 2.

## Phase 2 — ARCHITECTURE

Tradeoff discussion. Every decision records pros / cons / alternatives /
decision, saved as ADRs in `docs/adr/NNN-<slug>.md`.

- Application: stack, module boundaries, integrations, hosting.
- ML/data: data stack, pipeline orchestration, batch vs streaming, serving,
  experiment tracking, data versioning — plus modeling **constraints only**
  (latency, interpretability, compute budget, candidate approaches). The
  model choice itself is a loop-side exploration task, per the decision
  rule.

## Phase 3 — SYSTEM DESIGN

Fill `${CLAUDE_PLUGIN_ROOT}/templates/system-design.md` into
`docs/system-design.md`: the module table (module | responsibility |
inputs | outputs | depends on), data flow, repo layout, open questions.

**Approval gate:** your human partner approves before Phase 4.

## Phase 4 — ROADMAP

Derive `docs/roadmap.md`:

```markdown
# Roadmap

| # | Task | Mode | Realizes | Depends on | Status |
|---|------|------|----------|------------|--------|
| 1 | <task> | build | FR-1, FR-3 | - | pending |
```

`Realizes` carries the PRD requirement IDs the row delivers, so a task
inherits its acceptance criteria instead of restating them. Rows that
realize no requirement — spikes, infrastructure, every exploration row —
carry `-`; an exploration task answers a question rather than delivering
a capability, and citing an FR there is false precision.

- Application: rows from system-design modules in dependency order.
- ML/data: compile CRISP-DM phases 3-6 — data preparation → build rows;
  modeling → exploration rows (stopping rules will come from the PRD
  metrics); evaluation → inside the exploration rows; deployment → build
  rows via the promotion rule. Modeling rows inherit both the ML metric
  and the guard metric as their stopping-rule inputs.

**The roadmap is a queue, not a plan**: rows carry no specs or task
breakdowns — each row later gets its own `/start-task` run with full
discipline. Reorderable; outcomes insert and remove rows.

## Phase 5 — SCAFFOLD

**ML/data and hybrid projects:** scaffold from the ML Pipelines skeleton
at `${CLAUDE_PLUGIN_ROOT}/skeletons/ml-pipelines/` — read
`${CLAUDE_PLUGIN_ROOT}/skeletons/README.md` for the contracts and the
scaffolding steps (copy the self-contained tree → rename `src/PROJECT/`
→ set the pyproject name), and the scaffold's own README for the full
rename checklist. Confirm the trainer default (`configs/trainer/`) and
split protocol with your human partner from the PRD's scope. The
system-design repo layout should have been drawn from the skeleton tree
in Phase 3.

Then invoke `/new-project` (it will detect the existing docs and fill the
project CLAUDE.md from them). If the repo already existed, just commit the
genesis docs: `git add docs/ && git commit -m "docs: project genesis - prd,
architecture, system design, roadmap"`.

Close by pointing at the first roadmap row: "Genesis complete. Start with
`/start-task` on row 1."
