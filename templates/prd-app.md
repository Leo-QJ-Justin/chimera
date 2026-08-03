# {{PROJECT_NAME}} — PRD

## Problem statement
{{What hurts, for whom, today? Concrete, observable pain — not a solution
in disguise.}}

## Target audience
{{Who uses this? If "me", say what future-you needs to remember.}}

## Solution
{{What it is; how it addresses the problem; what it deliberately is NOT.}}

## Requirements
{{Numbered globally and never renumbered — roadmap rows and task specs
cite these IDs, so an ID keeps its meaning once assigned. A capability
with no testable "Done when" is not a requirement yet.}}

### FR-1: {{short capability name}}
{{Actor}} can {{capability}} {{under conditions}}.
- Done when: {{a testable condition — a command that exits 0, an
  observable output, a number. Never "handles X gracefully".}}
- Out of scope: {{optional — a bound this FR explicitly does not cover}}

## Success measures
- **Primary:** {{observable, not aspirational. "I use it weekly" beats
  "it's useful".}}
- **Guard (must not degrade):** {{what the primary must not be bought at
  the expense of — latency, cost, an existing workflow}}

## Non-goals
{{Explicitly out of scope for v1 — the YAGNI fence.}}

## Open questions
{{Numbered. Unknowns that become exploration tasks or ADRs, not silent
gaps.}}

## Assumptions
{{Tag inline as `[ASSUMPTION: ...]` wherever something above was inferred
rather than stated, and list every tag here for confirmation. An
unlabelled inference reads as a decision.}}
