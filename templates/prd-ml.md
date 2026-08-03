# {{PROJECT_NAME}} — ML/Data PRD

> CRISP-DM phases 1-2 in template form; phases 3-6 execute through the loop
> via docs/roadmap.md.

## Business understanding
- **Objective:** {{what decision or capability this enables}}
- **Business success criteria:** {{the real-world measure that matters}}
- **ML metric (proxy):** {{the offline metric that proxies the above — and
  why it's a fair proxy}}
- **Guard metric (must not degrade):** {{what the proxy must not be bought
  at the expense of — latency, precision when chasing recall, cost per
  inference, a subgroup's performance}}
- **Baseline to beat:** {{the dumb solution this must outperform: naive
  forecast, majority class, current manual process}}

The promotion threshold — how much better than baseline is good enough —
is set by the first exploration task and recorded in its findings, not
here. Genesis records the metric and the baseline; experiments settle the
number.

## Prediction target
{{The definitions that are expensive to discover are wrong three weeks
in.}}
- **Unit of analysis:** {{one row is one — customer? customer-month?
  session? sensor reading?}}
- **Label definition:** {{exactly what counts as positive, including the
  boundary cases}}
- **Prediction window:** {{how far ahead, from which point in time}}
- **Exclusions:** {{rows deliberately outside scope, and why}}
- **Known prevalence:** {{positive rate if known; "unknown until EDA" is a
  valid answer and becomes an early roadmap row}}

## Data understanding
- **Sources:** {{datasets, where they live, how they're obtained/refreshed}}
- **Access:** {{credentials, APIs, licensing constraints}}
- **Expected quality issues:** {{gaps, revisions, survivorship, delays}}
- **Initial EDA questions:** {{the first 3-5 things to look at}}

## Requirements
{{System capabilities only — what the pipeline must do. Model quality
lives in the metric fields above, never in an FR: a threshold written at
genesis is an invented number. Numbered globally and never renumbered;
roadmap rows and task specs cite these IDs.}}

### FR-1: {{short capability name}}
{{Actor or component}} {{capability}} {{under conditions}}.
- Done when: {{a testable condition — a command that exits 0, an
  artifact at a path, a latency figure. Never "handles X gracefully".}}
- Out of scope: {{optional — a bound this FR explicitly does not cover}}

## Constraints
{{These bound the modeling search; experiments settle the choice within
them (genesis-vs-loop rule).}}
- **Latency:** {{inference-time budget, if any}}
- **Interpretability:** {{required? for whom?}}
- **Compute/cost:** {{training + serving ceilings}}
- **Candidate approaches worth trying:** {{a shortlist, not a decision}}

## Non-goals
{{Explicitly out of scope — the YAGNI fence.}}

## Open questions
{{Numbered. Unknowns that become exploration tasks or ADRs, not silent
gaps.}}

## Assumptions
{{Tag inline as `[ASSUMPTION: ...]` wherever something above was inferred
rather than stated, and list every tag here for confirmation. An
unlabelled inference reads as a decision.}}
