---
name: writing-comparative-reports
description: Use when writing a report that compares many instances of one kind of thing — corpus profiling, tool comparison, log analysis — before any instance is opened
---

# Writing Comparative Reports

Two parts: the report contract (how a profile of many instances is
produced) and the narrative recipe (how a decision brief is built on
it). The `corpus-profiler` agent executes Part 1 mechanically over a
corpus; Part 2 is judgment and belongs to the human partner and the
main agent. A tool comparison or log analysis follows both parts with
no agent involved.

## Part 1 — The report contract

Compressed: rubric (with consumers) → same rubric per item →
cross-item table → per-item verdicts → regenerate, never patch.

1. **Rubric before reading:** declare the questions, criteria, and
   field checklist before opening any instance. Per-item sections
   become comparable; "what we looked for" is auditable separately
   from "what we found".
2. **Every criterion names its consumer** — the downstream decision
   that reads it, or the authority document (business goals, charter)
   that justifies it. A criterion with no consumer leaves the rubric.
3. **Define a location/provenance code alphabet once** (e.g. one
   letter per layer of the artifact) and use it in every dive. The
   alphabet is what makes dispersion questions askable: "what is the
   smallest set of layers a consumer must read?"
4. **Record negative evidence as diligently as positive:** "absent
   from all X" is a stated verdict per criterion per item, never an
   omission. Escalation and cost decisions read the negatives.
5. **Mechanism explainers ride with the numbers:** a criterion that
   needs a nontrivial detector documents the mechanism, validates it
   with at least two independent signals, shows a worked example, and
   cites sources. Pre-label adjacent known hazards even when the
   sample contains none.
6. **Two altitudes, both mandatory:** a cross-item summary table for
   distribution questions (thresholds come from here) and per-item
   deep dives for existence and shape questions (edge cases come from
   here).
7. **Every deep dive ends in a decision-relevant verdict,** not a
   summary.
8. **The rubric iterates on misses; the report regenerates whole** from
   a committed script and is never hand-patched. Frozen counts become
   test fixtures.

## Part 2 — From profile to brief (the narrative recipe)

The profile records what is; the brief decides what binds. These moves
are judgment — the human partner and the main agent make them, fed by
the profile's handoff sections (see the `corpus-profiler` output
contract), or, where the instances are outside artifacts rather than
the project's own, by the comparison itself. Moves 1 to 5 apply where a
profile exists; move 8 applies where the instances are products or
published methods; moves 6 and 7 always apply.

1. **Join the population authority.** Connect profiled items to the
   volume or importance source (a tracking list, usage data). Every
   coverage claim ("these 5 = 51%") comes from this join; profiling
   counts alone rank nothing. If no authority exists, say so — the
   brief then carries enumeration claims only.
2. **Make the constraint move.** Take the dominant observation
   (e.g. "23 of 25 files are PDF"), state it as a candidate rule,
   classify **every** item against the rule (a tier table), and give
   every violator an explicit disposition — excluded, manually
   admitted with a revisit trigger, or fix-required. A constraint
   without a full classification and violator dispositions is an
   observation wearing a rule's name.
3. **Name a reference implementation.** Pick the cleanest exemplar
   under the rubric and map it completely — every field on every part,
   each designated (extracted / cross-check / not extracted). This is
   what "good" means, and what standardisation requests point at.
4. **Ground the contract bidirectionally.** Every required field is
   confirmed present in the evidence; every request to a partner
   exists because the field is already observable and carries a
   compliance count showing the ask is cheap; the whole contract is
   tested against the sample ("none rejects").
5. **Carry conflicts live.** Each observed self-contradiction (two
   values for one field) travels into the open-decisions section with
   its values and sources as the worked example.
6. **Label every claim** Observed / Interpretation / Recommendation,
   and state causal cautions ("region is shorthand for which suppliers
   sit there, not a cause"). Where a claim comes from a third party,
   label it **documented** or **marketing** — a capability a vendor
   asserts is not a capability a vendor documents.
7. **Close per the evidence-closure rule** (chimera:exploring-reproducibly,
   Ending a Task): each adopted finding ends as evidence → constraint →
   implications, or "no design consequence."
8. **Where the instances are outside solutions** — products, published
   methods, a competitor's documentation — the report carries two more
   sections. *Mapping to this project*: for each mechanism found,
   whether this project's own evidence shows it is needed, citing the
   instance that needs it. *What we would not adopt and why*. An item
   enters the requirements only through the mapping's cited instance.
   The survey proposes; the project's evidence decides. A finding with
   no instance behind it is recorded as an open question, never as a
   requirement — that is the difference between learning from prior art
   and replicating it without understanding.
