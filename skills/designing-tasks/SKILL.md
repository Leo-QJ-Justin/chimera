---
name: designing-tasks
description: Use before any task-level creative work - building a feature or pipeline, adding functionality, or framing an analysis or experiment - explores intent and design before implementation
---

# Designing Tasks

Turn a task into an approved design through natural collaborative dialogue.

<HARD-GATE>
Do not implement, code, or open a notebook before presenting a design and
receiving approval. This applies to every task.
</HARD-GATE>

## Checklist

You MUST create a todo for each item and complete them in order:

1. **Explore context** — read the request or roadmap row, relevant files,
   docs, and recent commits. Read affected modules in system design. If a
   roadmap `Realizes` entry names PRD requirements, re-present each one's
   enumerated content for item-level confirmation; an ID is not consent.
   - **Check every premise about the data.** "X never prints Y", "every Z
     carries W" is a claim. Check pinned data and cite supporting instances
     or the counterexample. Verify external facts against their authority
     before making a ruling.
2. **Determine mode** — confirm build | exploration (set at /start-task);
   it decides what Step 4 produces.
3. **Ask clarifying questions** — one at a time, one per message; prefer
   multiple choice; focus on purpose, constraints, success criteria.
4. **Propose 2-3 approaches** — with trade-offs; lead with your
   recommendation and reasoning. YAGNI ruthlessly.
5. **Present the design** — use sections scaled to complexity; confirm each.
   Present rules per *Approve Against Cases, Not Prose*.
6. **Write the design doc** — `docs/specs/YYYY-MM-DD-<topic>.md`, commit it.
7. **Self-review** — check placeholders, consistency, scope, ambiguity, and
   any flow sketch against the file-depth budget. Then run:
   - **Instance check:** every statement of the form "the data does /
     never does" carries an instance citation — file, section, page, or
     a count over the pinned set. One without is a placeholder.
   - **Enforcement check:** every sentence of the form "X cannot
     happen" or "X is never emitted" names its validator or test. Without
     enforcement, enforce it or move it to Decisions with a false-making
     trigger. Fix inline; no re-review.
8. **User review gate** — "Spec written and committed to `<path>`. Please
   review before we write the implementation plan." Wait. Make requested
   changes.
9. **Transition** — invoke chimera:writing-plans. Nothing else.

## Mode Fork (what Step 4-6 produce)

**Build mode — task spec:**
- Behavior: what it does, observable outcomes, edge cases. Where the row
  names requirements, identify each realized `FR-N`; its *Done when* lines
  are acceptance criteria unless explicitly renegotiated. Any aggregate
  ships with its failing or differing instances: identity, expected,
  observed, verdict, and a stated cap, from the same code.
- Interfaces: exact inputs/outputs; if `docs/system-design.md` exists, name
  touched modules and honor their I/O contracts. **A type is not a form:**
  state each value's one representation, two or three inputs mapping to it,
  and its source rule. This binds fixtures, expected output, config, stored
  columns, and labelled data.
- Error handling and testing approach (per chimera:test-driven-development)
- Flow sketch (required when the task adds or reshapes modules): a short
  diagram tracing one input through named functions and files. If a call
  exceeds the project's depth budget, justify every hop or flatten it. The
  default is two files per call.
- Decisions: every judgment call the spec makes, listed as *decision /
  rejected alternative / trigger to revisit / supersedes*. *Supersedes*
  names what it replaces or "none"; Step 0b consumes it.

**Exploration mode — research brief:**
- Question: what are we trying to learn?
- Hypothesis: what do we expect and why?
- Data: which sources, which snapshot will be pinned
- Method: how we'll test the hypothesis; evaluation metric and guard
  metric, inherited from the PRD when present. A brief cites no FRs.
  Every aggregate ships with its failing or differing instances: identity,
  expected, observed, verdict, and a stated cap, from the same code
- **Decision line (mandatory): "What result would change what decision?"**
  A brief without this line is incomplete — it is the single guard between
  research and wandering.

If the task came from `docs/roadmap.md`, reference its row number in the
doc header.

## Scope Check

If the task actually spans multiple independent deliverables ("build the
pipeline and dashboard"), split it into roadmap rows before refining it.

## Decisions That Are the Human's Call

A Decisions section records judgment calls — but recording is not
consent. Some decisions must be asked as an explicit question (checklist
item 3) before the spec is written, never only recorded:

- Any heuristic placed in a correctness path: a fail-closed gate, a
  value-deciding rule, or acceptance fallback. The human chooses it or an
  honest alternative. If accepted with a revisit trigger, probe outside
  the sample and name one concrete wrong input. "A wrong case found in
  review" is not a trigger. The entry is incomplete without that case.
- Any renegotiation of a requirement's stated scope.

Litmus: if a reviewer could plausibly say "this cleverness does not
belong in a correctness path," the human decides at design time.

## Approve Against Cases, Not Prose

A rule described only in words is not reviewable. Before writing the spec:

- **A rule is presented as a worked example.** A comparator, matcher,
  ranker, canonical function, parser, or ordering is a table of three or
  more real inputs traced to outputs. A request for an example means the
  prose already failed.
- **A bulk artifact is produced one unit first.** Where a task produces
  many fixtures, migrations, generated configs, labels, or pages, produce
  one. List the judgment calls it forced that the interface did not cover,
  and get rulings before the rest are produced.

## Design for Isolation (build mode)

Each unit has one purpose and a defined interface: behavior, use, and
dependencies. Internals must change without breaking consumers.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "The task is obvious, skip to code" | Obvious tasks hide assumptions. The design can be five sentences — write them. |
| "Questions slow us down" | One wrong assumption costs more than five questions. |
| "I'll design as I implement" | That's implementation-first with narration. Design, approve, then build. |
| "The brief can come after a quick look at the data" | The quick look IS analysis. Brief first (chimera:exploring-reproducibly). |
| "The Decisions section records it, that's enough" | Recording is not consent. A heuristic in a correctness path is asked as a question, not filed. |
| "The spec describes the rule clearly" | A rule is understood through its cases. Show three real inputs traced to their outputs. |
| "It's the same judgment 18 times, just do them all" | Then one unit costs nothing and surfaces every choice before it is applied 18 times. |

## Terminal State

Invoke only chimera:writing-plans next. Do not implement or open a notebook.
