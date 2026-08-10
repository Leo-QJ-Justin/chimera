# {{PROJECT_NAME}} — AI Architecture

> The decisions an LLM, embedding, or retrieval component forces. Fill
> this when the system has one. Each resolved concern becomes an ADR; the
> reasoning, status, tier, and reversal cost live there, not here.
>
> Written in Simplified Technical English (ASD-STE100 register). Terms are
> defined in the PRD Terms table.

Two rules apply to every section below:

- Add a component only when you can name the requirement that forces it.
  A retrieval pipeline that solves the case does not become an agent.
- Never state a model name, context window, or price you cannot ground.
  Mark the assumed figure `[assumed — verify]` and say what to check.

**"None" is an answer.** Where a layer is not needed, write "none" and
the reason. A blank section is a gap; a stated "none" is a decision.

## Boundary: deterministic or probabilistic

Decide this before the sections below, because it decides what can be
tested. **If a decision can be unit tested, it is deterministic. If it
depends on domain judgment, tradeoffs, or incomplete context, it may stay
probabilistic.**

| Area | Decision | Boundary |
|---|---|---|
| {{input validation, defaulting, contract checks, orchestration}} | {{what it does}} | deterministic |
| {{interpretation, ranking, generation}} | {{what it does}} | probabilistic |

Anything probabilistic needs an output contract that fails closed:
name the check, and what the system does when the output breaks it.

## 1. Model

| Field | Value |
|---|---|
| Primary | {{model + tier}} |
| Why | {{the specific requirement it satisfies}} |
| Rejected alternative | {{model + one-line reason}} |
| Fallback | {{what to route to on failure or cost pressure}} |

{{State the assumed context window, and whether the workload is
latency-bound or throughput-bound. If the data is regulated, state
whether this is a hosted API or self-hosted, and why that is
defensible.}}

## 2. Embeddings

{{Model, dimensionality, and the chunking strategy it implies — size,
overlap, splitting boundary. State whether the domain vocabulary is
standard or specialised: that decides whether an off-the-shelf model is
adequate. Or: "none — reason".}}

## 3. Retrieval store

{{Recommendation and rejected alternative, judged on three axes only:
expected corpus size, filtering and metadata needs, and the operational
burden the team can absorb. Under roughly 100k vectors, state explicitly
whether no dedicated store is the correct answer.}}

## 4. Framework

{{An orchestration framework, or "none — direct SDK calls". Justify by
what the framework removes, not by what it offers, and name the lock-in
cost and the debugging cost you accept with it.}}

## 5. Interfaces

| Interface | Method | Purpose | Auth | Sync/Async |
|---|---|---|---|---|
| {{name}} | {{verb + path}} | {{what it is for}} | {{scheme}} | {{which}} |

{{Cover the contract this system exposes and the third-party services it
consumes. Flag any endpoint whose latency profile makes a synchronous
call unwise.}}

## 6. Memory

| Layer | Decision |
|---|---|
| Within-request context | {{what enters the window, and the eviction rule}} |
| Cross-turn / session | {{store, retention, what is kept and what is summarised}} |
| Long-term / user | {{what persists, and the deletion path}} |
| Caching | {{prompt cache, semantic cache, or none}} |

{{State the privacy consequence of everything that persists.}}

## 7. Deployment

{{Target environment, packaging, the scaling trigger, and the rollout
strategy for model and prompt changes — a prompt edit is a deployment.
Name the one thing most likely to break in production and the signal that
detects it. Match the sophistication to the scale in the PRD.}}

## 8. Evaluation

| Layer | What | Metric | Cadence |
|---|---|---|---|
| Offline | {{golden set}} | {{task-specific metric}} | {{pre-release}} |
| Online | {{production sample}} | {{quality and drift signal}} | {{continuous}} |
| Human | {{review loop}} | {{agreement rate}} | {{scheduled}} |

{{Name the metric specific to this system. "Accuracy" is a failed
section. State the minimum viable golden-set size and who realistically
produces it — evaluation plans die on the second question, not the
first.}}

## 9. Cost

{{Show the arithmetic. A total without its working is not an estimate.}}

1. **Unit assumptions** — {{tokens per request, requests per period,
   $/1M input and output tokens, infrastructure line items. Mark every
   price `[assumed — verify]`.}}
2. **Calculation** — {{the formula, visibly}}
3. **Range** — {{low / expected / high, where the spread reflects volume
   uncertainty, not vendor discounting}}
4. **Dominant driver** — {{the single line item worth optimising first,
   and the one lever that moves it}}

{{Without volume figures, give a cost per 1,000 requests instead of a
total, and raise the volume question in the PRD's open questions.}}
