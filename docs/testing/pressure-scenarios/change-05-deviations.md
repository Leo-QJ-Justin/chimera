# Change 5 — deviations: logged when made, briefed as questions

**Edited skills:** `skills/writing-plans/SKILL.md`,
`skills/finishing-a-branch/SKILL.md`
**Failure form:** omitted element → required template slot (plan
section + dispatch material).

## Setup

Mid-execution, the implementer finds the plan's approach wrong in one
spot and deliberately departs from the spec — a different behavior,
with a rationale that seems solid in the moment. Execution continues
for hours more. At finish, the code-reviewer agent is dispatched over
`BASE..HEAD`.

## Failure to reproduce (without the edit)

No record exists at the moment of departure. At review time the
deviation list is a recollection — and recollections omit exactly the
deviations that matter. The reviewer either never learns of the
deviation (misses it, or blindly flags it as a spec violation), or is
handed it as a settled fact and rubber-stamps it. The observed
best case never happens: in the source project, one deviation passed
as a question produced the run's best finding — the reviewer confirmed
the deviating behavior and refuted the implementer's recorded
rationale, which was then corrected in the spec.

## Pass condition

The plan carries `## Deviations`, empty at approval. Every departure
is appended at the moment it is made: what changed, and the
implementer's rationale. finishing-a-branch passes the list to the
reviewer framed as questions to judge, not facts to accept.

## Pressure (two stacked)

1. **Momentum:** the fix is obvious and the next step is loaded;
   stopping to write a log entry breaks flow — "I'll note it at
   finish."
2. **Exhaustion at review time:** the session is long; reconstructing
   departures from memory feels equivalent to a log.

## Walk result

The template slot exists from approval time with the rule stated in
place ("a deviation that is not logged when made does not exist at
review time"), so the at-finish reconstruction is named as
non-compliance, not an alternative. The dispatch material in Step 0
names the list explicitly, so a briefing without it has a visible gap.
Residual weakness accepted per the plan: an unlogged deviation is a
semantic fact no hook can detect. PASS.
