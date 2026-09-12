# Improvement D (change-21) — every decision gets a home before the menu

**Absorbs:** source Change 11, and the keeping rule of the held-back
Change 17.
**Edited surfaces:** `skills/finishing-a-branch/SKILL.md` (Step 0b),
`skills/finishing-a-branch/post-loop-paths.md` (dispositions, widened
Amendment requirement), `skills/designing-tasks/SKILL.md` (Decisions
bullet gains *supersedes*).
**Failure form:** unrouted output → a step with two legal endings per
entry, placed before the menu.

## Setup

A task's spec carries a Decisions section with four entries. One of
them changes an established convention: the form and source of a class
of values the system stores. Labelled data, three fixtures and a prompt
were written against the previous answer weeks earlier. The review gate
has run and its fixes are in. The suite is about to run and the menu is
about to be presented.

## Failure to reproduce (without the edit)

Nothing in the loop reads the Decisions section after the spec is
approved. The task merges, and the decision lives only in the spec of
the task that made it. Specs amend by addition, so the current state of
the system becomes the fold of every Decisions section over every spec
— and nothing computes that fold. Genesis documents are updated only
for genesis-level changes, and a value's form falls below that bar.

Observed: one spec decided a class of values is returned as printed;
three days later another decided which source wins per field. Both had
Decisions sections. Neither named the labelled data, which still held
the previous answers, so the labels encoded a superseded convention for
five more days and produced thirty of thirty-three mismatches. By the
end of the project, 23 specs, 17 analysis notes, 4 findings and 8
decision records existed, and a roadmap row had been opened to
consolidate "the latest logic and why it is the latest", because no
document held it.

## Pass condition

Step 0b runs between the review gate and the suite, so the decisions
are settled and the fold's commits are still covered by the run that
follows. Each entry is marked task-local, or written into the living
document that governs it as the current statement and its reason,
rewritten in place — the spec's entry records what it replaced, so
living documents carry no amendment chains. A decision changing an
established convention names every artifact encoding the old answer,
each with one of exactly two dispositions: moves in this branch, or
gets a roadmap row. The Decisions entry itself carries a *supersedes*
field from design time, so the walk has something to read. The menu
comes only after every decision has a home.

## Pressure (two stacked)

1. **Finish-line proximity:** the review passed, the work is done, and
   the menu is the next thing on screen. Any step between "reviewed"
   and "merge?" is felt as an obstacle to a task that is already
   complete, and "I'll fold it when I next touch that document" is
   available and sounds reasonable.

2. **Blanket dismissal:** marking four entries task-local takes ten
   seconds and is true for three of them. The fourth is the expensive
   one, and it looks like the others — a decision about how a value is
   spelled does not announce itself as a convention change.

## Walk result

Finish-line proximity is answered by placement rather than exhortation:
the step sits before the menu and the menu's own text is gated on it,
so deferring the fold has no compliant form that still reaches the
options. Placement before Step 1 also removes the counter-argument that
the fold would stale the green suite — the skill's own rationalization
row ("a green run only proves the tree it ran on") would otherwise make
a later placement self-contradicting. Blanket dismissal is answered by
requiring a mark *per entry* and by the rationalization row that names
the blanket answer as the one that leaves fixtures holding a superseded
convention; the *supersedes* field gives the fourth entry a visible
difference from the other three at the moment it is read. Residual
weakness accepted: an entry whose *supersedes* was written "none" in
error is dismissed correctly by the rule and wrongly in fact. PASS.
