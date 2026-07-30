# analysis-style + eda-profiler — Task Spec

**Mode:** build · **Approved:** in conversation, 2026-07-30 · **Evidence:**
[Micron](../research/2026-07-30-analysis-style-micron.md) and
[Mindef](../research/2026-07-30-analysis-style-mindef.md) mining reports.

## Goal

Encode Leo's analysis style as a reference file, and ship one mechanical
profiling agent, so exploration-mode work writes in Leo's voice and starts
from a drafted first pass. Per-topic EDA playbooks are explicitly DEFERRED
(Leo has further resources to trawl first).

## Deliverables

1. **`skills/exploring-reproducibly/analysis-style.md`** (~120 lines) —
   the style contract, loaded conditionally by the skill:
   - Dash rule: dashes are structural, never prose. Allowed as separators
     (heading suffixes, name/description pairs in tables and trees).
     Banned as clause joins inside sentences. Compound modifiers
     de-hyphenated in analysis text ("chi square test", "one parameter
     model"). Rationale on record: dash-heavy prose sounds AI-generated.
   - Observation cells: `Observations & Findings:` (plain text, colon)
     immediately after every non-trivial output; 2-4 bullets; quantity
     plus interpretation joined by "so"; no terminal periods; verbal
     hedges over spurious precision; every bullet ends in a decision or a
     flagged question; terse when nothing to say.
   - Training variant: bare `Findings` grouped by artifact + `Takeaway:`.
   - Decision tables before the code they govern.
   - Headings numbered and hierarchical; `---` before top-level sections;
     mandatory Limitations close; negative results kept on the record.
   - Chart conventions: titles state the takeaway (or untitled with
     markdown carrying it); single hue; value labels; stripped spines.
   - Notebook/report conventions in brief; provenance pointer to the two
     research docs.
2. **`agents/eda-profiler.md`** — mechanical first-pass profiler.
   Frontmatter: tools `Read, Grep, Glob, Bash` (writes nothing),
   model inherit. Dispatched with: dataset path, pinned-snapshot note,
   optional target column. Runs via python/pandas: shape + info, the
   missing/cardinality/example frame, three duplicate checks (full rows,
   key columns, coordinates if present), robust describe screens
   (relative near-zero variance, |skew| > 2, scale spread), target
   distribution if a target is named. Returns a draft in the style
   contract with a hard boundary: mechanical consequences may be stated
   as decisions; judgment-shaped items come back as flagged questions
   under "Judgment calls", never as decisions. Essential style rules
   embedded inline (agent stays self-contained); full contract referenced.
3. **Wiring** — `exploring-reproducibly/SKILL.md` gains a short
   `## Profile First (new datasets)` section after Pin Everything
   (dispatch the agent, adapt the draft, judgment stays yours) and a
   pointer to analysis-style.md in Notebook Conventions.
4. **Registration** — README (agents 1→2, style reference mentioned),
   CHANGELOG `[1.2.0]`, plugin.json + marketplace.json → 1.2.0.

## Edge cases

- Profiler must not proceed into feature decisions, imputation choices,
  or modeling — the boundary is the same one the style contract draws:
  facts and mechanical consequences only.
- Tiny or already-familiar datasets: the wiring is an offer, not a gate.
- Agent self-containment: core bullet-format rules embedded so the agent
  works even if dispatched outside a chimera checkout.

## Testing

Structural verification (sections present, frontmatter fields, versions,
cross-references resolve) + hook test suite. Behavioral pressure tests
deferred to v1.x evals, consistent with prior tasks.

## Self-review

No placeholders; names consistent (`eda-profiler`, `analysis-style.md`);
scope single-plan sized; verdict vocabulary for profiler output fixed
(decisions vs "Judgment calls").
