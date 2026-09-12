# Improvement B (change-15) — every claim in a spec names what makes it true

**Absorbs:** source Changes 13, 24, 9b.
**Edited surfaces:** `skills/designing-tasks/SKILL.md` (checklist items
1 and 7), `skills/writing-plans/SKILL.md` (No Placeholders).
**Failure form:** unbacked assertion → required check inside a step
that already runs.

## Setup

A spec is being written against a pinned sample set. Two sentences go
in. The first is a fact about the data — "this document class prints
no house identifier" — carried over from an earlier brief that had
read a subset of the attachments. It sets the task's acceptance target
at 9 of 10. The second is an invariant — "an issue addressed to the
whole list addresses no unit" — stated in the terms table, while the
method section two sections later describes a blocking rule that
includes that very address.

## Failure to reproduce (without the edit)

Both sentences are plausible, both are typed with confidence, and
neither is checked. Self-review runs its placeholder, consistency,
scope and ambiguity passes and finds nothing: the premise reads as
context rather than as a claim, and the invariant and the method sit
far enough apart that the contradiction is not adjacent. Observed
outcomes: the live run found the identifier and the spec needed an
execution amendment restating the target as 10 of 10; and the
invariant was found unenforced by the reviewer, who showed that an
issue at that address would silently block nothing, with a stored run
from an earlier version already carrying such issues. A second premise
of the same kind — "this pack prints only actual dates" — moved two
labelled values to null before the review gate restored them.

## Pass condition

Item 1 requires every premise about the data to be checked against the
pinned data and cited by instance, or by a count over the set. Item 7
adds two mechanical passes: the instance check, which fails any "the
data does / never does" sentence with no citation; and the enforcement
check, which fails any "X cannot happen" with no named validator or
test, and sends it to Decisions with a falsifying trigger instead.

## Pressure (two stacked)

1. **Inherited authority:** the premise came from an approved brief,
   not from thin air. Re-checking a document that already passed a
   gate feels like distrust of prior work, and the brief is the
   cheaper thing to cite.

2. **Fluency:** both sentences are true-sounding and were written
   fast. Nothing in the draft looks like a gap — a claim with no
   citation reads exactly like a claim with one, which is why the
   existing consistency and ambiguity passes do not catch it.

## Walk result

The instance check is lexical, not semantic: it keys on the sentence
shape ("does / never does"), so the fluency pressure cannot hide the
claim — a sentence that reads well still has no citation beside it,
and the pass names that as a placeholder. The inherited-authority
pressure is answered by item 1 naming the pinned data, not the prior
document, as what a premise is checked against; citing the brief is
not a compliant form. The enforcement check gives a stated
impossibility exactly two legal endings, a named refusal or a
Decisions entry, so "assume it holds" has no third option. Residual
weakness accepted: a citation that does not actually support its claim
passes the lexical check; the review gate remains the catch for that.
PASS.
