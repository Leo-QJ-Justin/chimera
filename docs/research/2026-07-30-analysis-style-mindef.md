# Analysis Style Mining Report — Mindef/QS Assessment

> Research artifact for chimera. Mined 2026-07-30 from the QS DS assessment
> submission: q1 distribution fitting, q2 classification, q3 visualization,
> scenario2 geospatial decision pipeline (16 numbered scripts, 1,910 LOC).
> Purpose: evidence base for chimera analysis-style codification and the
> per-topic EDA question. Sibling:
> [Micron report](2026-07-30-analysis-style-micron.md).

## Per-notebook processing steps

### q1 (distribution fitting, 36 cells)
Title + task-requirement table + provenance link + `Scope:` bullets →
§1 Data Preparation and Summary (1.1 load/filter → 1.2 Data Checks:
nulls, KEY UNIQUENESS, dupes → 1.3 Summary Statistics → 1.4 Distribution
Shape: paired linear+log hists) → §2 Choosing a Distribution Family — a
"Feature of the data | What it implies" DECISION TABLE → §3 Candidate
Distributions (LaTeX PMFs, no code) → §4 Goodness of Fit (hand-rolled MLE
→ chi-square → fit-vs-observed chart → QQ loglog) → §5 Conclusion
(**"The Collapse to a One Parameter Model"** — noticing r→0, deriving the
logarithmic limit analytically, refitting to confirm identity numerically;
5.2 Suggested Distribution; 5.3 Limitations).

Signature: simplifying the model DOWNWARD after it fits; "With 9,000
agents a chi square test rejects almost any model, so we compare the size
of the chi square values rather than the p values".

### q2 (classification, 96 cells)
1.1 Loading (parse explained in md BEFORE code) → 1.2 Peeking → 1.3
`info()` → **1.4 Missing Values and Field Cardinality** — the signature
profiling frame:
`pd.DataFrame({'missing': ..., 'n_unique': ..., 'example': df.iloc[0]})`
driving four feature decisions → 1.5 Duplicates (3 aligned prints incl.
coordinate dupes → "Rows are therefore not independent, so a random split
would leak") → §2 per-field EDA ending in a field → "What it tells us"
table → §3 Modelling: **3.1 Methodology as a "Consideration | Decision"
table before any code** → target construction → split → 3.4 Feature
Engineering (curated vs derived keyword flags BOTH kept, coverage metric
proving derived value; intuition scored as a baseline and reported
losing) → tuning → CV → §4: **4.1 "Metric | Why it is here" table before
computing metrics** → metrics vs DummyClassifier → per-class report with
blind-spot callouts ("With a single row, F1 can only be 0 or 1, so these
measure nothing") → confusion matrix → gain importance → **4.6 The Rows
We Got Wrong** → §5 Summary and Limitations.

Leakage discipline stated twice in prose ("a feature scored against the
holdout must not be built from the holdout's labels"; "y_test_true is
stored but not inspected").

### q3 (visualization, 14 cells)
Structurally inverted: NO observation cells — the finding IS the section
heading, prose precedes each chart. Blockquoted brief → approach/
assumptions → inline-transcribed data (justified) → named plotting-helper
cell with docstrings → numbered takeaway-sentence chart titles →
Implications (**argues against the brief's own framing**: subsidy is a
supply-side lever, leakage is a retention problem) → `## Justification of
design choices` as a required closing section.

### scenario2 (geospatial, 40 cells)
Rigid 4-block template x9: `## N.M Title (Q-ref)` → **Question.** →
**How to read.** → code → **Insights & Observations** bullets. Metric
definitions (LaTeX M1-M4) BEFORE any analysis. Figures deliberately
untitled — markdown carries the takeaway. "Checked once here, then set
aside" pattern for dimensions measured and dismissed on the record.

## The scenario2 pipeline convention

- 16 numbered scripts `00_`-`15_`, each with a uniform docstring contract:
  `Inputs:` / `Outputs:` (with column lists) / `Checks:` / `Usage:` —
  including the unimplemented 00 (spec committed before code).
- Linear dependency chain through **one hub table**
  (`block_features.csv`): "one place to look if a number is wrong".
- Dirs: data/raw + data/cache (gitignored, reproducible) / data/processed
  (committed derived) / data/manual (hand-assembled, every row
  source-linked, own README) / outputs/charts + outputs/tables (markdown
  evidence tables) / outputs/tier1_archive.
- **39 assert validation gates** under `# ---- validation gates ----`
  banners, ranges anchored to EXTERNAL truth ("LTA cites ~2/3 within 10
  min"), messages say what to do.
- **Two-tier accuracy with a recalibration hinge**: tier 1 uses the 1.2
  planning convention end-to-end; tier 2 measures ~10.8k real routes,
  finds 1.383, overwrites the hub table in place, re-runs downstream via
  subprocess, and DIFFS the conclusion against the archived tier-1 answer
  ("*** PHASE RANKING ORDER CHANGED ***" if moved). The convention itself
  becomes a finding.
- **Retrospective validation run blind on a real past event** (script 13:
  network filtered to opened < 2024.4, TEL4 as "future"), honest about
  what the check can and cannot validate.
- Sensitivity as a shipped artifact (`sensitivity.md`: weight sweeps,
  threshold sweeps, equity multiplier), cited by path from prose.
- Caching AS the reproducibility mechanism (MD5-keyed disk store, all API
  calls idempotent/resumable); rate limiting + retries in the client;
  fixed time snapshot instead of now(); seeds only where stochasticity
  exists (random_state=0 KMeans, 42 in q2), no global np seed.
- src division: geo (haversine + defended global choice), frequency (one
  vendor-quirk function), features (hub builder, tier contract stated),
  metrics (constants carry justification via #: comments), simulate
  (REUSES features+metrics — "what makes the retrospective validation a
  one-line network filter"; post-condition assert "adding stations cannot
  reduce coverage"), clients/ (all IO, no analysis).
- Conservative-direction choices stated ("understates, not overstates,
  each phase's case"); adversarial reading of measurement design
  ("crediting bus feeders as access would define away the disparity being
  measured").
- Deck figures regenerated from artifacts (script 15), never hand-drawn.

## Markdown/prose style

**Observation cells, three variants:**
- `Observations & Findings:` — PLAIN text (not bold), colon, `*` bullets.
  q1 (9x), q2 (22x). Immediately after the code cell it reads.
- `**Insights & Observations**` — bold, no colon, `-` bullets. scenario2
  (12x).
- None — q3 (headings carry findings).

Bullet form: quantity + interpretation joined by "so", 2-4 bullets per
cell, NO terminal periods in q1/q2 (0/31 and 1/65), verbal hedges ("about
2.7", "roughly 9 times") over spurious precision. Verbatim exemplar:

> Observations & Findings:
>
> * Mean about 2.7, variance about 24, so the variance is roughly 9 times
>   the mean. The data are overdispersed
> * Half the agents close a single sale
> * The maximum is 255, far above the mean, so the tail is heavy

**Decision tables before code** (the pre-commitment habit): "Feature of
the data | What it implies" (q1), "Consideration | Decision" and "Metric |
Why it is here" (q2), "# | Assumption | Justification" (scenario2).

**HYPHEN/DASH FINDING — the corpus splits:**
- Section 2 notebooks (q1/q2/q3): **zero em dashes, zero en dashes,
  compound modifiers actively de-hyphenated** — "Chi Square Test", "Per
  Class Report", "The Collapse to a One Parameter Model", "zero truncated
  negative binomial", "non negative counts", "one hot expansion", "5 fold
  stratified cross validation"; "percent" spelled out instead of %.
  This is the PURE FORM of the maintainer's stated no-hyphen preference.
- scenario2 + all READMEs + Micron: hyphenated compounds and em dashes
  used freely as primary structure.
- Codification decision (maintainer, 2026-07-30): dashes are STRUCTURAL, never
  prose. Rationale: dash-heavy prose "sounds very AI". Allowed: dash as a
  separator (heading suffix "## 2.1 Bar Chart — Target Distribution",
  name — description pairs in trees/tables). Banned: em/en dashes as
  clause joins inside sentences; hyphenated compound modifiers in
  analysis text (write "chi square test", "one parameter model"). The
  Section 2 notebooks are the reference form for prose; the Micron/
  scenario2 em-dash-in-prose habit is the deviation to avoid.
- Playbooks decision (maintainer, 2026-07-30): eda-playbooks DEFERRED — additional
  reference material is pending before writing per-topic playbooks; do
  not draft them from this corpus alone.

Headings: strictly numbered; `---` rule before every top-level `#`;
Title Case in q1/q2, sentence case in q3/scenario2; scenario2 appends
question IDs `(Q1.2)` for traceability. British spelling in prose,
American -ize in docstrings. Bold only on load-bearing numbers/terms.
Every notebook ends with Limitations / Named assumptions & limitations.

## The personal signature moves (top set)

1. Decision tables committed before the code that implements them.
2. `Observations & Findings:` as a fixed post-output cell — a bounded 2-4
   bullet read of THIS output, 43x across the corpus.
3. Measuring one's own intuition and reporting it losing.
4. Naming the metric's blind spot in the same breath as the number.
5. Simplifying the model downward after it fits.
6. Declining to over-recommend below the analysis's resolution ("The
   defensible recommendation is the programme, not a specific phase").
7. Arguing against the brief's framing when the data disagrees.
8. Two-tier accuracy with an explicit recalibration hinge + conclusion
   diff.
9. Blind retrospective validation on a real past event.
10. Assert gates keyed to external ground truth.
11. Setting a dimension aside, on the record, after measuring it once.
12. Conservative-direction choices stated explicitly.
13. Definitional move at the top of every open-ended problem ("'Experience'
    is subjective, so it is defined measurably as the anatomy of a
    journey").
14. Docstrings as executable contracts (Inputs/Outputs/Checks/Usage).
15. Plain-language domain asides mid-analysis + closing glossary.
16. Chart titles state the takeaway, not the variables; notebook figures
    untitled because markdown carries it; design-choice justification as a
    required closing section.

## README style

- Root: 133 words, pure routing table, no prose paragraphs.
- Per-section compact template: `# Section 2 · Question N — Title` →
  restating para → Deliverable → Data → Notebook structure (Section |
  Contents table mirroring notebook headings) → Result/Framing → Running
  it (identical nbconvert incantation).
- q2 README escalates to a 2,097-word standalone report (says things the
  notebook does not — the error-sink-as-taxonomy-overlap reframing; gain
  vs split-count importance justification).
- scenario2 README: full methods doc — problem decomposition (ASCII tree),
  assumptions table, per-metric LaTeX + **worked example after every
  formula**, evaluation checks table, 16-row script table with ⭐ on
  deliverable steps, data-sources table, limitations, plain-language
  glossary. Even .gitignore is commented with rationale.
