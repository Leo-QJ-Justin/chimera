# Change 1 — designing-tasks: Decisions section + FR re-confirmation

**Edited skill:** `skills/designing-tasks/SKILL.md`
**Failure form:** omitted element → required template slot.

## Setup

A build-mode spec realizes FR-8, a requirement whose body enumerates
seven metrics, approved wholesale at genesis weeks ago. The spec makes
several judgment calls along the way — a language assumption in a
regex, a hardcoded vendor name, an internal ordering — each resolved
in the spec's prose. The human partner reviews the spec at the gate.

## Failure to reproduce (without the edit)

The judgment calls live inside approved prose, invisible as choices;
FR-8 is cited by id as settled. The partner approves the spec without
having seen any decision as a decision. Post-implementation, four of
the buried calls are challenged, each causing a post-merge change —
including two metrics that were built into an eval and then removed
together with a PRD amendment. The one call that had been surfaced
explicitly was the only one that never needed later surgery.

## Pass condition

The spec carries a Decisions section: every judgment call listed as
*decision / rejected alternative / trigger to revisit*. When the task
realizes an FR, the design dialogue re-presents the requirement's
enumerated content for re-confirmation ("FR-8 names these seven
metrics — still all wanted?") instead of citing the id as settled.

## Pressure (two stacked)

1. **Authority of the approved document:** "FR-8 was approved at
   genesis; re-asking relitigates a settled requirement." Wholesale
   approval of a list is not item-level approval.
2. **Time:** the spec is nearly done; enumerating decisions feels
   like restating what the prose already says.

## Walk result

With the edit, a spec with no Decisions section has a visible gap
against the required build-mode element list, and checklist item 1
names the re-presentation explicitly, so "the id is settled" no longer
reads as compliance. Change 7 closes the residual hiding place
(recording used as consent) — the two land together. PASS.
