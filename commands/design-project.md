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

Ask a third only when an authoritative document corpus already exists —
prior design notes, audits, an execution roadmap, a ratified architecture:

3. **Brainstorm** or **distill**? Distill converts the corpus into the
   genesis artifacts; it does not re-litigate decisions the corpus already
   settled. Every approval gate below still applies — distillation changes
   the input, not the discipline.

## Register

Write every genesis document per chimera:writing-in-ste. Each one opens
with the register line that skill specifies. Run the rewrite pass before
each approval gate, never after: a document approved in one register and
rewritten in another is a second document that nobody approved.

## Phase 1 — DISCOVER

Brainstorm the idea conversationally — the problem, who it's for, what
success looks like. One question at a time; propose options with a
recommendation where useful. Then fill the type-matched PRD template into
`docs/prd.md`:

- Application → `${CLAUDE_PLUGIN_ROOT}/templates/prd-app.md`
- ML/data → `${CLAUDE_PLUGIN_ROOT}/templates/prd-ml.md` (CRISP-DM phases
  1-2: business understanding, data understanding, constraints)
- Hybrid → both templates' sections, merged (product shell + ML core)

**Distill mode only:** the PRD opens with a precedence header — the
ordered list of source documents, and the rule that these genesis docs
win where sources disagree. Without it, a stale audit and a fresh ADR
carry equal weight for the next reader.

**Self-check before presenting** — fix inline, no re-review:

1. **Substance** — cut any section that drives no decision.
2. **Done-ness** — every FR carries at least one testable *Done when*;
   no unmeasurable adjective survives ("gracefully", "reasonable",
   "user-friendly").
3. **Scope honesty** — every inference tagged `[ASSUMPTION]` and listed
   in the index; every omission stated in Non-goals rather than left for
   the reader to infer.
4. **ID integrity** — FR IDs unique and contiguous.
5. **Register** — the STE pass is run and the Terms table covers every
   term in the document that is not common English.

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

**When the system has an LLM, embedding, or retrieval component** — of
any project type — fill `${CLAUDE_PLUGIN_ROOT}/templates/architecture-ai.md`
into `docs/architecture-ai.md` first. It names the decisions such a system
forces (model, embeddings, retrieval store, framework, interfaces, memory,
deployment, evaluation, cost) and the deterministic-versus-probabilistic
boundary that decides what can be tested. Each resolved concern becomes an
ADR; the template holds no ADR field.

Each ADR carries four fields beyond the four above:

- **Status** — `proposed` (a spike settles it), `accepted`,
  `accepted, under challenge` (a later ADR contests it; name that ADR),
  or `superseded by NNN`. A live disagreement stays visible; silence is
  not resolution.
- **Tier** — the reversal cost, which is the build-order argument.
  Tier 1: adopt before the first roadmap row, unrecoverable later.
  Tier 2: adopt before the second consumer. Tier 3: reversible, recorded
  for completeness. Or: permanent constraint.
- **Reversal cost**, one line in Consequences — cost to reverse × chance
  of reversal × chance the project still exists then. This arithmetic is
  what separates a day-one decision from speculative generality.
- **Confidence** — `[High]`, `[Moderate — depends on X]`, or
  `[Low — verify before committing]`.

Two consolidation patterns keep the directory readable: small reversible
technology choices go in **one table ADR**, one row each, not one file
each; and deliberate shortcuts go in a **debt register ADR**, reviewed at
every gate row.

Every deferral — a debt-register entry, a deferred roadmap item, a future
improvement — is written as **trigger condition → change → unlock**. A
deferral with no trigger is a wish, and it never gets revisited because
nothing tells you when to look. Name one thing that would be
over-engineering today and correct at ten times the scale.

**Self-check before presenting** — fix inline, no re-review:

1. **Alternatives** — every decision names the option it beat, and why.
2. **Confidence varies** — if every tag reads `[High]`, the tradeoffs
   were not examined. Uniform confidence across a set of decisions is a
   claim nobody can hold.
3. **Forced components** — every component ties to a stated requirement.
   Remove the ones that do not.
4. **Triggers** — every deferral carries its trigger condition.

## Phase 3 — SYSTEM DESIGN

Fill `${CLAUDE_PLUGIN_ROOT}/templates/system-design.md` into
`docs/system-design.md`: the module table (module | responsibility |
inputs | outputs | depends on), data flow, repo layout, open questions.

Data flows and module pipelines are mermaid `flowchart`; schedules are
mermaid `gantt`. ASCII arrows are correct only for a single linear chain,
and repo layout stays a text tree.

**Self-check before presenting:** the STE pass is run, and every module
name in the table matches the name used in the PRD Terms table.

**Approval gate:** your human partner approves before Phase 4.

## Phase 4 — ROADMAP

Derive `docs/roadmap.md`:

```markdown
# Roadmap

> A slipped gate beats a false-green gate.

| # | Task | Mode | Realizes | Depends on | Status |
|---|------|------|----------|------------|--------|
| 1 | <task> | build | FR-1, FR-3 | - | pending |
| 4 | Gate: <what must hold> | exploration | - | 1-3 | pending |

Critical path: 1 → 3 → 4 → 7.
Parallel: rows 2 and 5 depend on nothing in the path above.
```

`Realizes` carries the PRD requirement IDs the row delivers, so a task
inherits its acceptance criteria instead of restating them. Rows that
realize no requirement — spikes, infrastructure, every exploration row —
carry `-`; an exploration task answers a question rather than delivering
a capability, and citing an FR there is false precision.

**Gate rows** sit after the rows they gate. Each is an exploration row
whose deliverable is a written go/no-go note in `docs/`, naming what was
checked and what the result permits. A gate with no written note did not
happen. The two footer lines cost three lines and answer the questions
every session opens with: what is blocking, and what can run now.

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
