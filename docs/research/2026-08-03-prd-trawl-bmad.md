# PRD Trawl — BMAD-METHOD

> Research artifact for chimera. Written 2026-08-03. Source:
> `bmad-code-org/BMAD-METHOD`, MIT (Copyright (c) 2025 BMad Code, LLC),
> `main` at commit date 2026-08-03. Chimera's PRD templates were
> originally modelled on this project; this pass re-reads the current
> version to decide what else belongs in ours. Read-only: nothing was
> copied verbatim into chimera.

## 1. Where the PRD lives now

The v4 `prd-tmpl.yaml` the original idea came from no longer exists. In
the current layout the PRD is a skill, `src/bmm-skills/plan/bmad-prd/`,
in three parts:

| Path | What it is |
|---|---|
| `assets/prd-template.md` | An "Essential Spine" of nine sections plus an "Adapt-In Menu" of conditional clusters |
| `assets/prd-validation-checklist.md` | A seven-dimension quality rubric run by a reviewer subagent |
| `SKILL.md` | The elicitation process: brain dump → stakes calibration → fast or coaching path → finalize |

Spine: Document Purpose · Vision · Target User (JTBD, non-users, user
journeys) · Glossary · Features (FRs nested) · Non-Goals · MVP Scope ·
Success Metrics · Open Questions · Assumptions Index. The Adapt-In Menu
adds clusters per product class — consumer, enterprise, regulated,
developer products, embedded.

Neighbouring skills in the same folder place the PRD in a chain:
`bmad-product-brief` and `bmad-prfaq` upstream, `bmad-architecture` and
`bmad-create-epics-and-stories` downstream. The epics template
(`plan/bmad-create-epics-and-stories/templates/epics-template.md`)
consumes the PRD through an explicit `FR Coverage Map`.

## 2. The five load-bearing devices

The section headings are not what carries the weight. These five
conventions are:

1. **Stable global IDs** — `FR-N`, `UJ-N`, `SM-N`, cross-referenced
   inline ("realizes UJ-3", "Validates FR-X"). Numbered globally so the
   IDs survive reorganisation of the sections around them.
2. **FRs carry testable consequences** — each FR ships with verifiable
   conditions. The template's own example: "System returns HTTP 429 when
   request rate exceeds 100/sec per merchant."
3. **Inline `[ASSUMPTION: ...]` tags round-tripped into an index** —
   everything the drafter inferred rather than heard is marked where it
   sits and listed at the end for confirmation.
4. **Counter-metrics** — named beside success metrics and described as
   equally load-bearing: they stop the builder optimising the wrong
   thing.
5. **A glossary with a no-synonym rule** — every domain noun defined
   once; a synonym anywhere else in the document is called a discipline
   violation.

Two supporting policies: length scales with stakes (hobby ≈ two pages,
internal tool five to eight, launch as long as its FRs require), and an
`addendum.md` sink keeps technical "how" out of the PRD.

The rubric's seven dimensions: decision-readiness, substance over
theater, strategic coherence, done-ness clarity, scope honesty,
downstream usability, shape fit.

## 3. Verdicts

Measured against chimera's genesis chain (`/design-project` → PRD, ADRs,
system design, roadmap) and its task loop (`/start-task` → spec → plan →
execute → verify).

| Device | Verdict | Reason |
|---|---|---|
| FR blocks with testable consequences | **adopt** | Chimera had no requirements anywhere: the module table and roadmap rows were derived from PRD prose, so `verifying-before-done` had nothing to check "requirements met" against but a row title |
| Stable global IDs | **adopt** (FR only) | One token that survives PRD → roadmap → spec → verification. `UJ`/`SM` IDs are not adopted because the artifacts they label are not |
| `[ASSUMPTION]` tags + index | **adopt** | An LLM drafting from conversation infers constantly; an unlabelled inference reads as a decision, which `rules/common/coding-style.md` forbids everywhere else |
| Counter-metric | **adopt**, renamed *guard metric* | One line, and it applies harder to ML than to product work — the proxy metric must not be bought at the expense of latency, precision, or cost |
| Open Questions section | **adopt** | Existed at system-design altitude, never at PRD altitude |
| Length scales with stakes | **reject** — *qualified 2026-09-01, see §7* | Considered and dropped: the maintainer's standing preference is the same meticulousness everywhere. Templates stay one-size at full rigor |
| Validation rubric, seven dimensions | **adopt in part** — four-point self-check | Substance, done-ness, scope honesty, ID integrity. "Shape fit" dies with the rigor dial; the rest is team-review apparatus. Placed in `/design-project` Phase 1, matching the self-review steps `designing-tasks` and `writing-plans` already carry |
| User journeys with named protagonists | **reject** | Theater for solo tools. The rubric's own "shape fit" dimension says as much about single-operator products |
| Standalone Glossary section | **reject**, absorbed — *reversed 2026-08-09, see §6* | The real need is ML-specific: unit of analysis, label definition, prediction window. That became `prd-ml.md`'s Prediction target section, which is where the ambiguity actually costs weeks |
| MVP Scope separate from Non-Goals | **reject** | Chimera's single Non-goals fence does the same work in half the space |
| Product brief, PRFAQ upstream | **reject** | `/design-project` Phase 1 is a conversation; a second upstream artifact adds a layer with one caller |
| `addendum.md` tech-how sink | **reject**, already solved | ADRs in Phase 2 and `docs/system-design.md` in Phase 3 hold the technical how, with better structure than a sink file |
| Run workspaces, memlog, reviewer subagents, headless mode | **reject** | Team-scale machinery for surviving handoffs between agents and roles; chimera has one operator and a committed git history |

## 4. What chimera already does better

- **ML/data has no equivalent in BMAD at all** — no proxy-metric honesty,
  no baseline to beat, no CRISP-DM shape. `templates/prd-ml.md` covers
  ground the source does not.
- **The genesis-vs-loop rule** — if an experiment could settle it, do not
  settle it by argument. This is why chimera's ML requirements cover
  system capabilities only and the promotion threshold is deferred to the
  first exploration task: an accuracy target written at genesis is an
  invented number. BMAD has no equivalent boundary.
- **Technical decisions have a structured home** (ADRs with pros, cons,
  alternatives) rather than an unstructured addendum.

## 5. Wiring decision

Adopting FR IDs only pays if something downstream reads them. The chain
as built: `docs/prd.md` FRs → roadmap `Realizes` column → the spec names
which FRs it realizes and inherits their *Done when* lines as acceptance
criteria → `verifying-before-done` builds its checklist from those lines
→ `/start-task` Phase 6 amends the PRD if the task renegotiated a
requirement.

Three boundaries hold the loop's existing shape:

- Every touchpoint is conditional on `docs/prd.md` existing. Most loop
  runs happen in repos without one, and the loop must never come to
  require genesis.
- Exploration rows realize no FRs. An exploration task answers a
  question; it inherits the metric, baseline, and guard metric instead.
- The FR is an upward citation the spec may renegotiate, not an authority
  over it. The spec still owns behaviour, edge cases, and interfaces; the
  plan still owns steps and tests.

## 6. Amendment, 2026-08-09

The Glossary rejection above is reversed. Both PRD templates now carry a
`## Terms` table. The reason is not a change of taste: chimera adopted
Simplified Technical English as the genesis register, and STE's central
rule — one word, one meaning — has nothing to anchor to without a table
naming which words those are. See
`2026-08-09-genesis-amendments-from-field-use.md` §3. Every other verdict
in §3 above stands.

## 7. Amendment, 2026-09-01

The "length scales with stakes" rejection above is qualified, not
reversed. The v2 improvement plan's Change 8 gives the
persistent-model-discovery skill a conditional trigger — a full TRD
when external consumers, audit trail, or migration cost fire; one PRD
line otherwise — and that is a form of stakes calibration. The
distinction that keeps the original rejection intact: BMAD scales
*rigor* (a dial over how carefully any document is written); the
trigger scales *scope* (a binary, evidence-based test of whether a
whole artifact applies at all). Documents that exist are still written
at full rigor. See `docs/specs/2026-09-01-v2-improvements.md`,
Change 8.
