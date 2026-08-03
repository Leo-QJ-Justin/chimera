---
name: designing-tasks
description: Use before any task-level creative work - building a feature or pipeline, adding functionality, or framing an analysis or experiment - explores intent and design before implementation
---

# Designing Tasks

> Adapted from Superpowers `brainstorming` (Jesse Vincent, MIT), slimmed to
> task altitude and made mode-aware. Project-level design (PRD,
> architecture, system design) is `/design-project`, not this skill.

Turn a task into an approved design through natural collaborative dialogue.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, open any notebook,
or take any implementation action until you have presented a design and your
human partner has approved it. This applies to EVERY task regardless of
perceived simplicity.
</HARD-GATE>

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every task goes through this process — a small utility, a one-metric EDA
pass, a config-driven pipeline stage, all of them. "Simple" tasks are where
unexamined assumptions cause the most wasted work. The design can be short
(a few sentences), but you MUST present it and get approval.

## Checklist

You MUST create a todo for each item and complete them in order:

1. **Explore context** — the task's spec source (roadmap row, request),
   relevant files, docs, recent commits. If `docs/system-design.md` exists,
   read it: which module(s) does this task touch? If `docs/prd.md` exists
   and the roadmap row's `Realizes` column names requirement IDs
   (`FR-N`), read those requirements.
2. **Determine mode** — confirm build | exploration (set at /start-task);
   it decides what Step 4 produces.
3. **Ask clarifying questions** — one at a time, one per message; prefer
   multiple choice; focus on purpose, constraints, success criteria.
4. **Propose 2-3 approaches** — with trade-offs; lead with your
   recommendation and reasoning. YAGNI ruthlessly.
5. **Present the design** — in sections scaled to complexity (a few
   sentences to ~200 words each); ask after each section whether it looks
   right.
6. **Write the design doc** — `docs/specs/YYYY-MM-DD-<topic>.md`, commit it.
7. **Self-review** — placeholder scan, internal consistency, scope check,
   ambiguity check. Fix inline; no re-review.
8. **User review gate** — "Spec written and committed to `<path>`. Please
   review before we write the implementation plan." Wait. Make requested
   changes.
9. **Transition** — invoke chimera:writing-plans. Nothing else.

## Mode Fork (what Step 4-6 produce)

**Build mode — task spec:**
- Behavior: what it does, observable outcomes, edge cases. Where the row
  names requirements, say which `FR-N` the spec realizes: their *Done
  when* lines are the acceptance criteria, to be satisfied or explicitly
  renegotiated, never quietly dropped. Without a PRD, state behavior
  directly as before.
- Interfaces: exact inputs/outputs; if `docs/system-design.md` exists, name
  the module(s) touched and write against their I/O contracts — never
  re-litigate the architecture inside a task
- Error handling and testing approach (tests are per
  chimera:test-driven-development)

**Exploration mode — research brief:**
- Question: what are we trying to learn?
- Hypothesis: what do we expect and why?
- Data: which sources, which snapshot will be pinned
- Method: how we'll test the hypothesis; evaluation metric and guard
  metric (inherit both from `docs/prd.md` if present). A brief cites no
  FRs — exploration answers a question, it does not deliver a capability
- **Decision line (mandatory): "What result would change what decision?"**
  A brief without this line is incomplete — it is the single guard between
  research and wandering.

If the task came from `docs/roadmap.md`, reference its row number in the
doc header.

## Scope Check

If the task actually spans multiple independent deliverables ("build the
pipeline and the dashboard and the alerting"), flag it immediately and
split into roadmap rows — each row gets its own trip through the loop.
Don't spend questions refining a task that needs decomposition first.

## Design for Isolation (build mode)

Break the work into units with one clear purpose each, communicating
through defined interfaces. For each unit you should be able to answer:
what does it do, how do you use it, what does it depend on? If internals
can't change without breaking consumers, the boundaries need work.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "The task is obvious, skip to code" | Obvious tasks hide assumptions. The design can be five sentences — write them. |
| "Questions slow us down" | One wrong assumption costs more than five questions. |
| "I'll design as I implement" | That's implementation-first with narration. Design, approve, then build. |
| "The brief can come after a quick look at the data" | The quick look IS analysis. Brief first (chimera:exploring-reproducibly). |

## Terminal State

**The ONLY skill you invoke after designing-tasks is chimera:writing-plans.**
Do not invoke implementation skills, do not start coding, do not open a
notebook.
