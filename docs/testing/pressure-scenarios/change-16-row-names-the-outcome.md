# Improvement F (change-16) — a queue row names the outcome, not the method

**Absorbs:** source Change 16.
**Edited surfaces:** `commands/design-project.md` (Phase 4),
`commands/start-task.md` (Phase 6).
**Failure form:** ambiguous rule → sharpened clause naming what a row
may not carry, and where a held proposal goes instead.

## Setup

A session finishes a task and, in the same conversation, works out how
the next piece of work should be done: a named comparator per field
class, an extra bucket in the report, containment matching for one
field. The assessment is good and was expensive to reach. Phase 6 adds
the new roadmap row. The obvious way to keep the thinking is to put it
in the row.

## Failure to reproduce (without the edit)

Phase 4's rule says rows carry "no specs or task breakdowns". A named
comparator is neither a spec nor a task breakdown, so the row passes
the rule as written and lands carrying the method in full. The next
session picks the row up and its design phase inherits three decisions
nobody approved. Observed: the design phase rejected two of the three
after reading the data — one measured a case a validator would make
impossible, the other would have passed three labelled values that
appear nowhere in the source. The row either binds the design phase to
an unapproved decision, or costs it the work of unwinding one.

## Pass condition

Both places where rows are written name what a row states — the
question or deliverable, the decision it settles, its mode, its
dependencies — and what it does not: the method, the comparator, the
metric shape, the file layout. A row carrying a method is named as a
spec that skipped its approval gate. Where a proposal exists, the row
cites the note that holds it as an input, and the design phase weighs
it rather than inheriting it.

## Pressure (two stacked)

1. **Loss aversion:** the assessment took real work and exists only in
   chat. Stripping the method out of the row feels like throwing it
   away, and no other slot is obvious at the moment the row is
   written.

2. **Apparent compliance:** the existing rule was read and satisfied.
   "Rows carry no specs or task breakdowns" is true of the row as
   drafted — the author checked, and the check passed. Nothing signals
   that a second reading was intended.

## Walk result

The clause closes the reading that let the row through: it enumerates
method, comparator, metric shape and file layout as things a row does
not carry, so apparent compliance with "no specs or task breakdowns"
is no longer sufficient. Loss aversion is answered in the same
sentence rather than left to the author's judgment — the cited note is
named as the row's legitimate input, so the thinking has a destination
and stripping the row is not discarding it. Residual weakness
accepted: a note can itself be written as a spec and cited as though
it were evidence; the design phase's own approval gate is the catch,
and the clause says the phase weighs the note rather than adopting it.
PASS (predicted).

**Evidence status:** this verdict is reasoned against the edited text, not
yet produced by a walk. A walk loads a fresh session with only the edited
file, presents the Setup, and applies both pressures in order. Until one
runs, read the verdict as a prediction — the same standard improvement B
applies to a spec premise.
