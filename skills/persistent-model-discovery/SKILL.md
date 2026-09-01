---
name: persistent-model-discovery
description: Use during /design-project Phase 1b (BIND) when the system has external consumers, reproducibility needs, schema migration costs, compliance needs, or AI provenance requirements - locks the persistent model in docs/technical-requirements.md before the PRD is written
---

# Persistent Model Discovery

Lock the persistent model — grain, immutability, corrections,
consumers — before the PRD is written. A schema discovered
mid-implementation costs a full rework; a schema locked at genesis is
designed once. The persistent model is one interlocking design: its
four parts cannot be approved as separate decisions, so it gets one
artifact, the TRD.

## Trigger (conditional)

Invoke when the system has ANY of:

- External consumers (API, database, data feed others depend on).
- Reproducibility needs (ML, experiments, audit trail).
- Schema migration costs (expensive to change post-ship).
- Compliance needs (audit trail, data retention, regulatory).
- AI systems with training-data versioning, model provenance, or
  reproducibility requirements.

**When NOT triggered:** no file. Write one line in the PRD
("Persistence: mutable state, single user, resets acceptable") and
proceed. A document whose entire content is one sentence is ceremony.

## The six questions

Checklist — create a todo per question; each is answered with your
human partner, never inferred:

1. **Grain:** what is one row in the primary table?
2. **Immutability:** what never changes, and why?
3. **Corrections:** when values must change, what is the mechanism —
   mutation, versioning, append-only, or frozen?
4. **Consumers:** who queries this data, and what questions must be
   answerable — including months later?
5. **Scope boundaries:** what is in scope, what is out, why?
6. **Failure modes:** what makes this system wrong if the immutability
   discipline is skipped?

## Deliverable

`docs/technical-requirements.md` (TRD), answering:

1. What is the persistent model? (ER sketch, grain, primary keys.)
2. What is the immutability policy? (What never changes, why, where.)
3. What is the correction policy?
4. Who are the downstream consumers, and what history must they see?
5. What are known constraints? (From profiling, feasibility,
   compliance — cite the BIND entries.)
6. What are the failure modes if the discipline is skipped?

**Approval gate:** your human partner approves the TRD before PRD
writing.

## Relation to ADRs

The TRD is the persistent model's one home. To keep the ADR index
complete, Phase 2 records a one-line Tier-1 ADR: "Persistent model per
`docs/technical-requirements.md`; reversal cost: schema migration with
data backfill." One home for the design, one pointer in the decision
index; never two competing homes.
