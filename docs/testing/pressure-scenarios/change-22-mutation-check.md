# Improvement H (change-22) — new behaviour's tests are proven by an executed mutation

**Absorbs:** source Change 22, narrowed.
**Edited surfaces:** `agents/code-reviewer.md` (Ground Rules,
Build-Mode Rubric).
**Failure form:** assertion accepted as evidence → an executed check
that produces the evidence.
**Status:** conditional experiment. Revisit after ten build reviews;
demote if it finds nothing and costs minutes every time.

## Setup

A build task merges a new behaviour with four new tests beside it. The
tests pass. The plan's steps show the test-first cycle, and the commits
are ordered test-then-implementation. The reviewer is dispatched over
`BASE..HEAD` with the spec, the Global Constraints and the deviations
list.

## Failure to reproduce (without the edit)

The rubric asks whether each new function has a test. It does, so the
check passes. But a test that asserts the wrong thing, or asserts on a
value derived from the code under test, passes exactly as convincingly
as one that constrains the behaviour, and the diff cannot tell them
apart. `writing-good-tests.md` carries a mutation check, but it is
*mental*, performed by the *author*, at *write* time — precisely the
party and the moment with the least ability to see the gap. Watching a
test fail is required during execution and leaves no artifact anyone
can read afterwards.

Observed: on one task the reviewer, unprompted, reduced a placement
step to identity and removed a denominator rule in a scratch copy, and
reported that exactly five new tests and one evaluation test turned red
and nothing else moved. That is the only check in the loop that proves
a test-first cycle was honest after the fact, and it took minutes.

## Pass condition

For each behaviour the spec names as new, the reviewer copies the tree
outside the working tree, reduces that behaviour to identity or removes
it, runs the suite in the copy, and reports the mutation with the exact
set of tests it turned red. A new test that stays green has proven
nothing. Ground Rules permit exactly this one write — outside the
working tree, HEAD untouched. Where the mutation changes nothing at all
the result is reported inconclusive with the reason, never "uncovered".
Where the suite is too slow, the report says so rather than skipping
silently.

## Pressure (two stacked)

1. **Existing green:** the tests pass, the cycle was followed, and the
   commits prove the ordering. Everything visible says the behaviour is
   covered, so running a mutation feels like distrust of a process that
   was followed correctly.

2. **Read-only identity:** the agent's first Ground Rule is that it
   never modifies files, and it has no Write/Edit tools. Copying a tree
   and editing it reads as a violation of the rule the agent was most
   firmly given, so the safe-looking action is to skip the check.

## Walk result

Existing green is answered by naming what green does not prove: the
rubric states that a tautological test satisfies the old
count-the-tests check, so "the tests pass" is no longer a compliant
answer to "is it covered". The read-only conflict is resolved in the
Ground Rule itself rather than left for the agent to adjudicate — the
permitted write is scoped to a disposable copy outside the working
tree, and the Write/Edit clause is kept intact, so the guarantee that
mattered is not weakened to buy the check. The inconclusive guard stops
the check's most dangerous failure: an editable install makes the copy
import the original package, the suite runs unmutated, and "zero tests
killed" would otherwise be indistinguishable from genuinely uncovered
behaviour. Residual weakness accepted: the check costs one suite run
per new behaviour, which is why it is bounded. This scenario needs a real
repository to walk: the chimera repo has three test scripts and no package
under test, so there is no behaviour here to reduce to identity.
PASS (predicted).

**Evidence status:** this verdict is reasoned against the edited text, not
yet produced by a walk. A walk loads a fresh session with only the edited
file, presents the Setup, and applies both pressures in order. Until one
runs, read the verdict as a prediction — the same standard improvement B
applies to a spec premise.
