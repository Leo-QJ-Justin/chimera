# {{PROJECT_NAME}} — ML/Data PRD

> CRISP-DM phases 1-2 in template form; phases 3-6 execute through the loop
> via docs/roadmap.md.
>
> Written in Simplified Technical English (ASD-STE100 register): short
> sentences, active voice, simple tenses, one meaning per term.

## Terms
{{One row per term that is not common English. One meaning each — the
document uses the term this way everywhere. Delete the section if empty.}}

| Term | Meaning |
|---|---|
| {{term}} | {{one sentence, no synonyms}} |

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
- **Exclusions:** {{rows deliberately outside scope, and why}}
- **Known prevalence:** {{positive rate if known; "unknown until EDA" is a
  valid answer and becomes an early roadmap row}}

### Issue schedule
{{Time series only — delete for cross-sectional problems. A forecast is
not specified until all eight rows are fixed. Leakage, evaluation, and
serving all read from this table.}}

| Property | Value |
|---|---|
| Issue frequency | {{how often a prediction is made}} |
| Issue time | {{at what instant; configuration, but recorded per forecast}} |
| As-of cutoff | {{what data the forecast may read — the issue time, by contract}} |
| Target set | {{exactly which future intervals one issue covers}} |
| Resolution | {{how long one predicted interval is}} |
| Lead-time range | {{nearest and farthest interval, as durations}} |
| Output shape | {{point, quantiles, or joint distribution; per interval or drawn jointly}} |
| Re-issue policy | {{may the same target be forecast again, and under the same id}} |

**Shape:** {{fixed-event (one issue covers one whole target period) or
rolling t+1}}

**Worked example:** {{one issue with concrete timestamps — issued at
<time>, covers <intervals> of <date>, leads <range>; may read <sources>,
must not read <sources>; scored against <final data> at <lag>. The
example is what forces the ambiguity out: reviewers catch timing bugs in
concrete numbers that they miss in prose.}}

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
