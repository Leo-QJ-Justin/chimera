# Improvement C (change-17) — interfaces pin form; aggregates ship their instances

**Absorbs:** source Changes 9a and 10.
**Edited surfaces:** `skills/designing-tasks/SKILL.md` (Behavior,
Interfaces and Method bullets), `skills/writing-plans/SKILL.md`
(per-task Interfaces block),
`skills/verifying-before-done/SKILL.md`.
**Failure form:** under-specified element → explicit correction in the
bullet that already claimed to cover it.

## Setup

Two tasks, weeks apart. The first produces an artifact a later task
compares against; its schema types four fields as strings and the spec
calls each value "the normalized target", stating the normal form for
two fields of sixteen. The second builds a harness that scores the
system against that artifact and reports a match rate per field.

## Failure to reproduce (without the edit)

The Interfaces bullet says "exact inputs/outputs", and a bare `str`
looks like compliance — the author checked the bullet and the check
passed. The producer then picks a form per field while working; the
consumer, built later, picks a different one. Observed: thirty of
thirty-three mismatches were the two conventions disagreeing, not the
system being wrong, and 700 values had to be edited once the forms
were finally written down.

The harness reports the rates alone. One field scores 0.100. Nothing
in any output shows a single pair behind that number, so the result is
recorded as a model-behaviour question and parked for five days across
four roadmap rows. In that window three separate sessions each write
a throwaway script that re-runs the harness's own pairing just to
print the differing pairs, and none is kept. When the pairs are
finally seen, the diagnosis takes one reading.

## Pass condition

The Interfaces bullet is written as a correction — "a type is not a
form" — and requires the one spelling each value takes, two or three
inputs that map to it, and the source rule where several places can
supply it, binding anything a later task compares against or stores.
The same correction appears in the plan's per-task Interfaces block.

Any aggregate the spec defines ships with the instances behind it: the
failing or differing ones, with identity, expected, observed and
verdict, bounded by a stated cap, emitted by the code that computes
the aggregate. `verifying-before-done` refuses the claim outright — an
aggregate whose instances cannot be listed is not verified.

## Pressure (two stacked)

1. **Apparent compliance:** the bullet already says "exact". The
   author wrote a precise type, believed the requirement met, and has
   no signal that a second thing was being asked for. This is the
   pressure that defeated the unedited text.

2. **Volume:** the aggregate runs over thousands of rows. "One row per
   instance" is obviously wrong at that size, so the whole requirement
   reads as impractical and gets dropped rather than bounded.

## Walk result

The correction form defeats apparent compliance: "a type is not a
form" names the exact mistake the compliant-looking answer makes, and
the worked contrast (`str` against a stated representation with its
source) leaves no reading in which a bare type satisfies the bullet.
The volume pressure is answered inside the rule rather than left to
judgment — the requirement is the *failing or differing* instances
under a *stated cap*, not one row per instance, so the impractical
reading is not the rule. `rules/common/coding-style.md` requires
labels to match epistemics, and a capped listing says what it is.
Residual weakness accepted: a spec can state a form that later proves
wrong; that is a decision to supersede, which improvement D routes,
not a gap here. PASS (predicted).

**Evidence status:** this verdict is reasoned against the edited text, not
yet produced by a walk. A walk loads a fresh session with only the edited
file, presents the Setup, and applies both pressures in order. Until one
runs, read the verdict as a prediction — the same standard improvement B
applies to a spec premise.
