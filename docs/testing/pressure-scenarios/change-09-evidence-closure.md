# Change 9 — findings close as constraints, not verdicts

**Edited surfaces:** `skills/exploring-reproducibly/SKILL.md`,
`agents/code-reviewer.md`
**Failure form:** omitted element → required template slot (closing
contract lines + rubric line).

## Setup

An exploration task profiles evidence that a downstream phase must be
designed against. The analysis is thorough, the numbers reproduce
from the pinned snapshot, and the findings doc ends with a compliant
decision line: `Decision: adopt <finding> because <numbers>`. The
exploration-mode review checks the decision line and passes it.

## Failure to reproduce (without the edit)

The doc is "information without implications": findings and a
verdict, but no commitment the next phase can design against. In the
source project two such documents passed the decision-line check and
still left every downstream design question open. A third version
added no new evidence — it reframed the same evidence as commitments
with named implications ("the parser can assume the 3-file reference
structure") — and only that version unblocked design. Adopting a
finding without naming its implications is how "interesting findings
limbo" happens.

## Pass condition

Every adopt decision carries its consequence chain:
`Decision:` + `Constraint: <what we now commit to>` +
`Implications: <named consequences, or "no design consequence">`.
`reject` and `park` keep the one-line form. The code-reviewer's
exploration rubric checks the chain, so an adopt without it is an
IMPORTANT finding, not a pass.

## Pressure (two stacked)

1. **Completion pull:** the decision line is written and the rerun is
   green; the task feels done — "the implications are obvious from
   the numbers."
2. **Exhaustion:** the analysis was long; naming design consequences
   feels like starting the next task early rather than finishing this
   one.

## Walk result

The closing contract makes the missing lines a visible gap in the
document itself, and the rubric line gives the reviewer an explicit
check that the old decision-line check did not cover — the exact hole
the two passed-but-useless documents fell through. The
"no design consequence" escape keeps the rule honest where a finding
truly binds nothing. PASS.
