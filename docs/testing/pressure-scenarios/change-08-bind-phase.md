# Change 8 — /design-project: BIND phase before PRD approval

**Edited surfaces:** `commands/design-project.md` (Phase 1b),
`skills/persistent-model-discovery/SKILL.md` (new),
`templates/prd-app.md`, `templates/prd-ml.md`,
`templates/system-design.md`,
`docs/research/2026-08-03-prd-trawl-bmad.md` (§7 amendment).
**Failure form:** omitted element → required phase + template slots.

## Setup

Genesis for a system whose business requirement reads simply
("extract records from submissions"). The spike produced evidence: a
dominant input format with two violators, wide variation in submitter
quality, and downstream consumers who will query the stored data
months later. The system stores data others depend on — the
persistent-model trigger fires.

## Failure to reproduce (without the edit)

The PRD is written straight from the brainstorm and spike findings.
The persistent model is discovered mid-implementation, when the human
partner works backward from "what does a database consumer querying
this six months from now need to trust?" — driving a full schema
rework (immutable sources, append-only corrections, dual status
fields) that the design documents then trail by a whole rework. The
format requirement and scope boundary never become commitments either:
every downstream design question stays open because the evidence
closed as findings, not constraints.

## Pass condition

Phase 1b converts evidence into commitments, each written as
evidence → constraint → implications, in three kinds: format/input
requirements, scope boundaries, and — when the trigger fires — the
persistent model via the six questions, producing an approved
`docs/technical-requirements.md` before PRD writing. The PRD's
"Commitments realized" section cites them; the system-design preamble
matches the TRD verbatim; Phase 2 records the one-line Tier-1 ADR
pointer. Untriggered projects write one PRD line and no file. An entry
whose implications name no design consequence stays in the spike
report.

## Pressure (two stacked)

1. **Simplicity illusion (authority of the requirement):** "extract
   records from submissions" reads as too simple to need a persistence
   design — the failure is invisible at PRD time by construction.
2. **Time:** the partner wants to see a PRD; a second gated phase
   before it feels like process for its own sake.

## Walk result

BIND is a named phase with its own approval gate, so skipping it
leaves a structural hole (the PRD template's required "Commitments
realized" section has nothing to cite). The trigger checklist makes
"does the persistent model need locking?" a mechanical test rather
than a feel; the six questions force the consumer-working-backward
move at genesis instead of mid-implementation. The scope-not-rigor
distinction is recorded in the trawl doc §7 rather than drifting
silently past a standing rejection. PASS.
