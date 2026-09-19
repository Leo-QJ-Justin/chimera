# Improvement A (change-18) — a rule, a form or a shape is approved against concrete cases

**Absorbs:** source Changes 9c, 12, 21, and the skeleton-first step of
the held-back Change 17.
**Edited surfaces:** `skills/designing-tasks/SKILL.md` (new section,
the correctness-path bullet, checklist item 5, Rationalizations),
`skills/writing-plans/SKILL.md` (Task Right-Sizing).
**Failure form:** unreviewable presentation → required form for the
presentation, plus a task-shaping rule.

## Setup

Three shapes of the same task, run at different times. (a) A spec
defines a comparator and describes it in prose. (b) A spec places a
containment heuristic in a correctness path, asks about it as the
skill requires, and records the answer with the revisit trigger "a
misplacement found in review". (c) A task will produce eighteen
labelled files whose schema types four fields as strings; all eighteen
can be drafted in one working day.

## Failure to reproduce (without the edit)

(a) The prose is approved because it reads well. Observed: the same
question came back three times in a row — "show me with an example",
"explain it like I am 5", "I'm having trouble visualizing this" — and
the rule became clear only as a traced walkthrough. The same session
had earlier shown a different rule as a table of input pairs with
verdicts, and that one was understood at once.

(b) The heuristic is built. The reviewer then enumerates three
misplacements in minutes, from short aliases matching inside longer
unrelated names, with no warning emitted. Your human partner rules a
two-line change. Six inputs typed at design time would have produced
the same ruling before any code.

(c) All eighteen are drafted and approved together, so no form choice
is seen before it has been applied eighteen times. The forms are
written for the first time nineteen days later, and 700 values move.

## Pass condition

A rule is presented as three or more real inputs traced to their
outputs in a table, before or instead of prose. An accepted
correctness-path heuristic's Decisions entry names at least one
concrete input it gets wrong, found by probing with inputs from
outside the sample; "a wrong case found in review" is not a trigger.
A bulk artifact is produced one unit first, the judgment calls that
unit forced are listed, and your human partner rules on each before
the rest are produced — the first unit is its own plan task.

## Pressure (two stacked)

1. **Fluency of the author:** the rule is clear *to the person who
   designed it*. Writing three traced cases feels like explaining
   something already explained, and the prose genuinely does describe
   the rule correctly.

2. **Batch economics:** eighteen units is one focused afternoon.
   Stopping after the first to wait for a ruling breaks the run, and
   the remaining seventeen are "the same judgment again" — which is
   precisely the claim that has not been checked.

## Walk result

The fluency pressure is answered by naming the observable symptom
rather than appealing to clarity: if your human partner asks for an
example, the prose has already failed. That converts a judgment call
about one's own writing into a prediction that has been wrong before.
The batch-economics pressure has no compliant form once the first unit
is its own plan task — Task Right-Sizing states the split meets the
existing reviewer criterion rather than bending it, so "fold it into
one task" contradicts the skill it would have to cite. The
rationalization rows close both restatements. Residual weakness
accepted: three cases chosen by the rule's author can all be cases the
rule handles; sub-trigger (ii) is the counterweight, requiring an
input the rule gets wrong, and the review gate remains the backstop.
PASS (predicted).

**Evidence status:** this verdict is reasoned against the edited text, not
yet produced by a walk. A walk loads a fresh session with only the edited
file, presents the Setup, and applies both pressures in order. Until one
runs, read the verdict as a prediction — the same standard improvement B
applies to a spec premise.
