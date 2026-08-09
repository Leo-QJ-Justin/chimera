# Genesis Amendments from Field Use

> Research artifact for chimera. Written 2026-08-09. Source: a
> `/design-project` run of chimera 1.6.0 over an existing document corpus
> (a time-series forecasting project, distilled rather than brainstormed).
> The maintainer recorded seven deviations from stock chimera that proved
> worth keeping, plus one that did not generalize. This document records
> what shipped, what changed against an earlier recorded decision, and
> what was deliberately not adopted.

## 1. What shipped

| # | Amendment | Landed in |
|---|---|---|
| 1 | STE as the genesis register | `skills/writing-in-ste/`, wired into `using-chimera` routing and every `/design-project` phase gate |
| 2 | Terms table in both PRD templates | `templates/prd-app.md`, `templates/prd-ml.md` |
| 3 | Mermaid instead of ASCII sketches | `templates/system-design.md` |
| 4 | Issue schedule for time-series PRDs | `templates/prd-ml.md` §Prediction target |
| 5 | Distill mode for genesis | `/design-project` Phase 0 and Phase 1 |
| 6 | Enriched ADR format | `/design-project` Phase 2 |
| 7 | Gate rows in the roadmap | `/design-project` Phase 4 |

## 2. The STE port

The capability came from `danyuchn/asd-ste100-skill` (MIT), which
repurposes ASD-STE100 — a controlled-language standard for aircraft
maintenance documentation — for text an agent must parse without a human
present. Chimera **ports** it rather than referencing it: the external
skill is one install away from absent, and a genesis gate that silently
does nothing when a skill is missing is worse than no gate.

Two boundaries carried over from the source and are kept deliberately:

- The standard's ~900-word approved dictionary is **not** reproduced.
  Chimera applies the principle (pick the plainest word, use it the same
  way every time) and points at the free official download for
  word-by-word compliance.
- STE is not applied to text where voice is the point. READMEs, PR
  narratives, and commit bodies stay in the house register.

The rule categories are paraphrased from ASD-STE100 Issue 9 (January
2025), maintained by the Simplified Technical English Maintenance Group.

## 3. A reversal, recorded

`docs/research/2026-08-03-prd-trawl-bmad.md` rejected BMAD's standalone
Glossary section: "theater for solo tools", with the real need absorbed
into the ML template's Prediction target section.

That decision is **reversed** by amendment 2, and the reason is amendment
1, not a change of taste. STE's central rule is one word, one meaning.
Without a table naming which words those are, the rule has nothing to
anchor to, and the field run showed domain nouns drifting between the PRD
and the system design. The Terms table earns its place now because a rule
depends on it; on its own, in a corpus without STE, the earlier verdict
still stands.

## 4. Why the issue schedule is a correctness item

Stock `prd-ml.md` specified a forecast with one line: how far ahead, from
which point in time. That is not enough to build against. Eight
properties are needed — issue frequency, issue time, as-of cutoff, target
set, resolution, lead-time range, output shape, re-issue policy — and the
as-of cutoff is the leakage contract in disguise. A system whose
as-of cutoff is unstated cannot be audited for leakage at all.

The worked example with concrete timestamps is the load-bearing part.
Reviewers catch timing errors in dates and durations that they read past
in prose.

## 5. Not adopted

**Skipping the ML-pipelines skeleton at Phase 5.** The field run
scaffolded its own tree and lifted individual components (run artifacts,
tracking) out of the skeleton instead of copying it. That rested on
project-specific evidence: a ratified build-versus-buy analysis, and a
conflict between the skeleton's Hydra configuration layer and that
project's single-config-authority rule. For a greenfield ML project the
skeleton copy remains correct, so Phase 5 is unchanged.

Recorded here so the next reader knows the deviation was examined and
declined, not overlooked.
