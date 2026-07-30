# {{PROJECT_NAME}} — ML/Data PRD

> CRISP-DM phases 1-2 in template form; phases 3-6 execute through the loop
> via docs/roadmap.md.

## Business understanding
- **Objective:** {{what decision or capability this enables}}
- **Business success criteria:** {{the real-world measure that matters}}
- **ML metric (proxy):** {{the offline metric that proxies the above — and
  why it's a fair proxy}}
- **Baseline to beat:** {{the dumb solution this must outperform: naive
  forecast, majority class, current manual process}}

## Data understanding
- **Sources:** {{datasets, where they live, how they're obtained/refreshed}}
- **Access:** {{credentials, APIs, licensing constraints}}
- **Expected quality issues:** {{gaps, revisions, survivorship, delays}}
- **Initial EDA questions:** {{the first 3-5 things to look at}}

## Constraints
{{These bound the modeling search; experiments settle the choice within
them (genesis-vs-loop rule).}}
- **Latency:** {{inference-time budget, if any}}
- **Interpretability:** {{required? for whom?}}
- **Compute/cost:** {{training + serving ceilings}}
- **Candidate approaches worth trying:** {{a shortlist, not a decision}}

## Non-goals
{{Explicitly out of scope — the YAGNI fence.}}
