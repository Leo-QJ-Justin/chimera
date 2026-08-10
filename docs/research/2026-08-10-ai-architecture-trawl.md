# AI Architecture Trawl — ai-system-architect

> Research artifact for chimera. Written 2026-08-10. Source:
> `sagarika29/ai-system-architect`, MIT, branch
> `cursor/python-llm-scaffold` at push date 2026-08-08. The project is a
> CLI that turns a use-case description into a structured architecture
> draft. Read-only: nothing was copied verbatim into chimera.

## 1. What the repo contains

The tool itself is a thin CLI over one model call. The transferable
material is three documents:

| Path | What it is |
|---|---|
| `src/ai_system_architect/prompts/system_prompt.md` | The concern checklist: 15 output sections with word budgets, plus an eight-item self-audit and a banned-phrase list |
| `docs/architecture-boundaries-base.md` | The deterministic-versus-probabilistic split, with a table mapping each area of the system to its recommended boundary |
| `src/ai_system_architect/core/validation.py` | An output contract: regex per required section, and a fail-closed error when one is missing |

The input schema (`core/request.py`) is four fields — deployment target,
data sensitivity, scale, approved stack — each with an explicit `Unsure`
value that must surface as a stated assumption rather than resolve
silently.

## 2. The gaps it exposed in chimera

1. **No AI-specific architecture concerns.** `/design-project` Phase 2
   listed topics for applications and for ML/data pipelines. Nothing
   covered a system that calls a model per request: model choice,
   embeddings, retrieval, memory, evaluation layers, cost. Chimera's ML
   path measures models; it never architected one.
2. **No risk artifact.** Not in the PRD, not in the system design, not in
   the ADRs.
3. **No cost dimension.** For a system billed per token this is a
   correctness gap, not missing polish.

## 3. Verdicts

| Device | Verdict | Reason |
|---|---|---|
| Nine AI concern areas | **adopt** | Shipped 1.8.0 as `templates/architecture-ai.md`; folded into `templates/system-design.md` in 1.8.1 — see §5. The concerns all survive, in one file rather than two |
| Memory as four explicit layers | **adopt** | Within-request, cross-turn, long-term, caching, with "none" as a recorded decision. The privacy consequence of what persists is stated |
| Cost with visible arithmetic | **adopt** | Unit assumptions, the formula, a low/expected/high range, and the dominant driver. Every price marked `[assumed — verify]` |
| Evaluation in three layers | **adopt** | Offline, online, human. The clause that earns its place: state the minimum golden-set size **and who realistically produces it** — evaluation plans die on the second question |
| Deterministic-vs-probabilistic boundary | **adopt** | "If a decision can be unit tested, it is deterministic" is a portable rule, and it decides what an output contract can check |
| Confidence tags with a variance check | **adopt** | ADRs gain a Confidence field; the Phase 2 self-check carries the rule that uniform `[High]` means the tradeoffs were not examined. Fits the standing labels-match-epistemics rule |
| Risk table with a detection signal | **adopt** | Landed in `templates/system-design.md`. The detection-signal column is the load-bearing part, and it wires to the roadmap gate rows added in 1.7.0 |
| Deferrals as trigger → change → unlock | **adopt** | Stated once in Phase 2, where the debt register is defined, and applied to chimera's own deferred CHANGELOG entries |
| "Commit to one recommendation" | **already covered** | `designing-tasks` step 4 leads with a recommendation; ADRs record the alternative |
| Clarification gate on a thin brief | **already covered** | Phase 1 is a conversation that elicits the same material; a word-count refusal fits a one-shot tool, not a gated dialogue |
| 1,400-word budget, one-shot output contract | **reject** | Designed for a single model call with no human present. Chimera's genesis is a multi-phase conversation with an approval gate per phase; a global word ceiling would cut material a gate exists to examine |
| Banned-phrase list | **reject** | `rules/common/documentation.md` §Register already forbids selling, superlatives, and rhetoric |
| Mechanical output validator | **considered, not adopted** | Chimera's own `creating-skills` rule says to automate what a regex can enforce, which argues for a genesis-doc checker. The maintainer declined it for now; it stays available as a future item rather than a silent omission |

## 4. Why the concerns became a template (superseded by §5)

*The reasoning below chose a separate template over a Phase 2 checklist.
The first two arguments held; the third did not survive review. Read §5
for what shipped.*

The alternative was a checklist inside Phase 2. Three arguments decided
it:

- Three of the nine concerns are tables, not questions — memory layers,
  evaluation layers, cost arithmetic. A command bullet cannot hold them.
- Chimera separates structure from process: templates hold document
  shape, commands hold the phases. A nine-section document inside a
  command inverts that.
- A checklist discussed in Phase 2 and never written down produces no
  artifact. The concerns would survive only in whatever ADRs happened to
  get created.

The template names which decisions must exist and what each must resolve.
The reasoning, status, tier, reversal cost, and confidence stay in the
ADRs, so no field appears in both.

## 5. Folded into system design, 2026-08-10

`templates/architecture-ai.md` shipped in 1.8.0 and was removed in 1.8.1.
Its content is now a section of `templates/system-design.md`. §4 asked
the wrong question — separate template or inline checklist — and never
asked whether an artifact that already existed was the right home.

Three overlaps forced it, each producing the same symptom: one question,
two files to open.

- **Sections 1-4 duplicated the ADRs.** Model, embeddings, retrieval
  store, and framework each recorded a decision, its reasoning, and its
  rejected alternative. That is an ADR, written beside the real ADR. They
  are now Phase 2 ADR topics, named in the command, with no second home.
- **Section 5 duplicated the module table.** External contract in one
  file, module I/O contracts in another. External interfaces now sit
  beside the module table.
- **The boundary table's rows were modules.** "Retrieval is
  deterministic, generation is probabilistic" is a property of a module,
  filed away from the modules. It is now a column on the module table.
  Section 7 Deployment had the same fault in miniature: target
  environment and packaging are hosting decisions, which belong to an ADR
  and the repo layout.

What remained — memory layers, evaluation layers, cost — are whole-system
properties, the same kind of thing as the risk table that already lived
in system design. There was no principled reason for risks to sit in one
file and cost in another.

The one real objection is timing: cost and model choice belong at Phase
2, where ADRs are written, while system design is Phase 3. When a Phase 3
cost estimate undermines a Phase 2 decision, that ADR takes status
`accepted, under challenge` and names the system design as the
challenger. The vocabulary shipped in 1.7.0 for exactly this case.

Result: two architecture artifacts. ADRs answer why this and not that.
System design answers what the system is.
