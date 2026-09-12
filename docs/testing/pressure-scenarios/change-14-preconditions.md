# Improvement E (change-14) — preconditions proven before task 1; splits stay findable

**Absorbs:** source Changes 19, 20a; relocates 20b.
**Edited surfaces:** `skills/writing-plans/SKILL.md` (header template),
`commands/start-task.md` (Phases 1 and 4),
`skills/finishing-a-branch/post-loop-paths.md` (split note).
**Failure form:** omitted element → required template slot + a phase
step that runs before the first task.

## Setup

A nine-task plan is approved. Task 7 re-records ten calls through a
third party's live API; the plan names the probe command inside that
task's steps, where it belongs topically. Tasks 1 to 6 are ordinary
local work with no external dependency. The session starts Phase 4 and
works the plan in order.

## Failure to reproduce (without the edit)

Nothing runs the probe until Task 7 is reached. By then Tasks 1 to 6
and 8 are written, tested and committed. The credential is expired.
The work that depends on it cannot proceed and the work that does not
is already on the branch, so the row can neither finish nor cleanly
stop. The observed cost: a stash, then a work-in-progress branch, a
scope split ruled by the human partner, an execution amendment to the
spec, and a reorder of two roadmap rows. The stash then conflicted
with four files edited in between, because a stash is session-local
and the tree moved under it.

## Pass condition

The plan header carries `## Preconditions` — every external resource a
task step needs, with the one command that proves it live now, or
"none". Phase 4 runs all of them before Task 1. A failure stops the
phase: the resource is renewed, or the plan is reordered so the tasks
needing it come last, or they are split into a later row — while no
task has started and the reorder is free.

When work does leave a task, it goes on a named branch, never a stash,
and the split is named in three places: the inheriting roadmap row,
the hand-off, and an execution amendment to the current spec. A row
that names a parked branch re-validates its notes by trial rebase
before design, because every merge since the split has moved the tree.

## Pressure (two stacked)

1. **Topical correctness:** the probe command genuinely belongs to
   Task 7 — that is the task that uses it. Hoisting it to the top of
   the phase looks like misfiling. "It is already in the plan, in the
   right place."

2. **Cost asymmetry at the moment of choice:** running five commands
   that will obviously pass, before any real work, reads as pure
   ceremony. Six of the seven probes have never failed. The expected
   value of skipping feels positive on every individual run.

## Walk result

The plan header makes `## Preconditions` a slot that exists at
approval time, so an empty one is visible as an omission rather than
an absence, and "none" is a stated answer rather than a silence. Phase
4 names the run as its first action, ahead of the task list, so the
topical-correctness rationalization has no compliant form: the probe
stays in Task 7's steps *and* its command appears in the header. The
cost-asymmetry pressure is answered by the phase text itself, which
names what skipping buys — a dead dependency found with every earlier
task already committed. Residual weakness accepted: a probe that
passes at task 0 and expires during a long execution is not caught by
this edit; the circuit breaker catches it as a failure during
execution instead. PASS.
