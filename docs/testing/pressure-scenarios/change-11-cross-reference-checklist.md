# Change 11 — /design-project: genesis cross-reference checklist

**Edited surface:** `commands/design-project.md` (self-checks in
Phases 1b, 1c, 2, 3).
**Failure form:** omitted element → required self-check lines
(extending the command's established fix-inline pattern).

## Setup

A v2 genesis run produces roughly seven artifacts — spike report,
brief, commitments, TRD, PRD, ADRs, system design — with load-bearing
cross-references: the PRD cites BIND entries, the TRD realizes them,
an ADR points at the TRD, the system-design preamble restates the
TRD's grain and consumers. Late in genesis, a commitment is reworded
during the BIND approval discussion.

## Failure to reproduce (without the edit)

Nothing re-checks the web after the rewording. The PRD's "Commitments
realized" section cites a commitment that no longer exists in that
form; an FR quietly contradicts the reworded scope boundary; the
system-design preamble states a grain the TRD no longer uses. This is
the exact failure the source project exhibited: design documents that
lead the shipped code, and requirement labels that stop matching
behavior — now multiplied across seven artifacts.

## Pass condition

Each phase's existing self-check carries reference-integrity lines,
run fix-inline before its approval gate: 1b — commitments trace to a
spike finding or brainstorm statement, violators have dispositions,
the TRD cites the BIND entries it realizes; 1c — every cited
commitment exists in Phase 1b's output, no FR contradicts a
commitment, FR IDs contiguous in the same pass; 2 — the Tier-1 ADR
pointing at the TRD exists when a TRD does, deferrals carry triggers;
3 — the preamble's grain, immutability policy, and consumers match the
TRD verbatim, module names match the PRD Terms table.

## Pressure (two stacked)

1. **Fatigue at scale:** by Phase 3 the operator has approved six
   documents; another checklist pass feels like re-reading finished
   work.
2. **Local-change blindness (sunk cost):** the rewording was approved
   in conversation, so it feels already handled — the cost of
   re-walking its citations is paid by documents that "didn't change."

## Walk result

The lines live inside the self-checks the command already runs before
every gate — no new ceremony, no reviewer subagent — so skipping them
means visibly skipping a named check step rather than forgetting an
unstated norm. The human approval gate remains the review; the
checklist is the cheaper equivalent of BMAD's reviewer subagent at
solo scale. PASS.
