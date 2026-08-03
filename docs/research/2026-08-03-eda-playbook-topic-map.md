# EDA Playbooks — Topic Coverage Map (synthesis)

> Research artifact for chimera. Written 2026-08-03 as Pass 4 of the EDA
> trawl — no new reading; this synthesizes the three trawl passes plus
> the two 2026-07-30 analysis-style reports into per-topic verdicts and
> the open questions for the maintainer discussion. Inputs:
> `2026-08-03-eda-trawl-atlas.md` (stated practice),
> `2026-08-03-eda-trawl-all-assignments.md` (practiced technique),
> `2026-08-03-eda-trawl-ai-eng-curriculum.md` (external cross-check),
> `2026-07-30-analysis-style-micron.md` (practiced: tabular/imbalance),
> `2026-07-30-analysis-style-mindef.md` (practiced: count/geospatial).
> Nothing here is a drafted playbook; per the 2026-07-30 deferral
> decision, drafting waits for the maintainer discussion recorded at the
> end of this document.

## 1. Coverage matrix

Columns: **practiced** (the maintainer's own project/coursework code),
**stated** (the vault's notes), **external** (the third-party
curriculum, reference only). Depth grades follow the source docs.

| Topic | Practiced | Stated (Atlas) | External (curriculum) |
|---|---|---|---|
| tabular | deep — A1P1 four-branch fill-in; A4P2/P3 canon; Micron missing-indicator/SMOTE-rejection; mindef q2 profiling frame | thorough — generic EDA spine, cleaning workflow, splitting/encoding, imbalance table | deep — five lessons with decision flowcharts |
| count | moderate — mindef q1 is a complete worked count analysis (overdispersion, family decision table, GOF); otherwise only summary counts inside tabular work | partial — countplot path, imbalance-degree table, chi-square guide; no dedicated note | deep on the imbalance/rare-event side (AUPRC, MCC, Precision@k); no dispersion/Poisson content |
| time-series | deep — A6P1 four-branch fill-in, the densest notebook in the corpus | thorough — stationarity, forecastability "Step 0", ACF/PACF, decomposition tables, TS outliers | deep — one dedicated lesson (rolling-stats stationarity check, lag-selection, target-alignment trap) |
| geospatial | thin — mindef scenario2 only, and it is a decision pipeline (metrics, validation gates, tiered accuracy) more than EDA technique; no map/CRS/spatial-autocorrelation EDA anywhere | absent — zero notes | absent — zero lessons |
| text/NLP | deep — A7P1 four-branch fill-in (audited cleaning, stemmer bake-off, BoW/TF-IDF comparison; peers add artifact taxonomy, vocabulary tracking, bigrams) | thorough — `EDA for NLP` 12-section sequence | moderate — one preparation lesson plus two production disciplines (version-pinned tokenization, train/inference parity) |
| images | moderate-deep — A5P2 four-branch fill-in (class balance, color separability, resolution scans, hypothesis-driven augmentation); A5P1 thin | thorough — `EDA for Images` is the vault's single most complete per-topic guide | moderate — single-image tensor hygiene only; dataset-level image EDA is a gap in the external source itself |
| generic spine (cross-topic) | moderate — first-pass ritual, before/after validation, finding-to-action closers recur across every notebook | thorough — 5-stage EDA order, 8-step cleaning workflow, which-test decision tree, split-then-scale rule | shallow — workflow framing only |

## 2. Per-topic verdicts

Verdict scale: **draft-ready** (evidence supports writing the playbook
now) | **assemble** (enough evidence, but scattered — the playbook is a
synthesis job, not a lift) | **defer** (evidence below the bar the
2026-07-30 decision set; do not draft from this corpus alone).

- **tabular — draft-ready.** Three independent sources agree on the
  spine; branch divergences supply concrete adopt/avoid calls (Cramér's
  V and target-conditioned profiling in, dtype-recast-before-correlation
  as a named trap). Richest topic in the corpus.
- **time-series — draft-ready.** The strongest topic: A6P1 practiced
  depth, the vault's forecastability/decomposition/outlier decision
  tables, and the curriculum's target-alignment trap compose into a
  near-complete playbook with almost no gaps.
- **text/NLP — draft-ready.** The vault's 12-section sequence and
  A7P1's audited-cleaning discipline reinforce each other; two
  independent branches converging on the POS-lemmatization fix gives a
  confirmed defect to warn about. The curriculum adds the two
  production-parity disciplines nothing else covers.
- **images — draft-ready, pending a scope decision.** Not on the
  original candidate list, yet the vault's most complete note and the
  corpus's most process-explicit EDA notebook both target it. Needs the
  maintainer to add it to the list before drafting (question 1 below).
- **count — assemble.** mindef q1 is a genuinely complete worked
  example (variance/mean overdispersion read, "Feature of the data |
  What it implies" family table, GOF with the chi-square-at-scale
  caveat, collapse-to-one-parameter move), but it is one analysis; the
  vault and coursework only touch count data as summary statistics
  inside tabular work. A count playbook is buildable by assembling
  mindef q1 + the imbalance-degree table + the chi-square guide +
  the curriculum's rare-event metrics — thinner than the four topics
  above, but with a practiced backbone.
- **geospatial — defer.** All three trawl passes return zero EDA
  technique content: no CRS handling, no map-based EDA, no spatial
  autocorrelation. scenario2 proves the maintainer has practiced
  geospatial *pipeline* discipline, but its EDA content is the generic
  profiling frame applied to spatial columns. Drafting from this corpus
  alone is exactly what the 2026-07-30 decision prohibits; keep
  deferred until reference material with real spatial-EDA technique
  arrives.

**Cross-cutting, not a topic: the generic spine.** The vault's 5-stage
EDA order and 8-step cleaning workflow, the corpus's first-pass ritual
and before/after validation pattern, and the which-significance-test
decision tree recur across every topic. Two structural candidates fall
out of this: a shared generic playbook (or preamble) that per-topic
playbooks extend, and the statistical-test decision tree as a shared
appendix rather than a per-topic repeat.

## 3. Confirmed defects and anti-patterns worth encoding

Findings strong enough that a playbook should name them as traps, each
corroborated by at least two independent observations in the corpus:

- **POS-less lemmatization** silently defaults to noun and never
  reduces verbs — two branches independently applied the same fix.
- **Impute-before-justify circularity** in time series — a
  forward-filled series is maximally autocorrelated, so persistence
  statistics computed after global ffill partly measure the imputation.
  The correct order (reason from ACF on real gaps, then impute) is
  practiced on the maintainer's branch.
- **Un-recast coded categoricals in correlation frames** — an ordinal
  code left numeric produced a spurious 0.66 correlation in one branch;
  a non-cyclic wind-direction code fed to Pearson/periodogram analyses
  in another. Same root cause, two independent instances.
- **Findings without actions** — imbalance measured but no downstream
  decision; duplicates detected but never dropped. The
  finding-to-action closer (practiced in A1P1/A5P2, formalized by a
  peer's per-stage observation blocks) is the antidote.

## 4. Open questions for the maintainer

1. **Topic list.** Evidence supports: tabular, time-series, text/NLP,
   images draft-ready; count as an assembly job; geospatial stays
   deferred. Confirm images joins the list and geospatial stays out
   until new material lands.
2. **Form and home.** Default candidate:
   `skills/exploring-reproducibly/playbook-<topic>.md`, loaded
   conditionally the way `analysis-style.md` already is. Decide: one
   file per topic, plus a shared generic playbook the per-topic files
   extend, or fold the generic spine into `SKILL.md` itself?
3. **The statistical-test decision tree.** Shared appendix referenced
   by playbooks, or a section repeated where relevant?
4. **External candidates.** The curriculum contributes 8 accepted-class
   candidates (stationarity rolling-stats check, Isolation Forest/LOF,
   AUPRC/MCC/Precision@k, mutual information, permutation importance
   with its evaluation-boundary caveat, NLP production-parity
   disciplines, image-tensor audit). Adopt into playbooks as clearly
   attributed external practice, or hold until practiced at least once?
5. **Vault hygiene (side finding, not playbook work).** Pass 1 found an
   identical uncited code block duplicated across two notes, one note
   self-marked "safe to delete", and one broken stub. Fix in the vault
   independently of this task, or ignore?

## 5. Decisions (maintainer, 2026-08-03)

1. **Topic list: the draft-ready four only** — tabular, time-series,
   text/NLP, images. Count waits with geospatial until more
   count-specific material accumulates; both remain deferred, not
   dropped. Images is added to the list on evidence strength.
2. **Form and home: per-topic + shared base** —
   `skills/exploring-reproducibly/playbook-<topic>.md`, one file per
   topic, loaded conditionally the way `analysis-style.md` already is,
   plus `playbook-generic.md` holding the 5-stage spine, 8-step
   cleaning workflow, and first-pass ritual that per-topic files
   reference instead of repeating.
3. **Statistical-test decision tree: shared appendix** —
   `playbook-stat-tests.md` with the vault's decision tree and the
   Shapiro-Wilk/Levene gating checks, referenced from each playbook.
4. **External candidates: adopt with attribution** — the eight
   accepted-class curriculum candidates enter the playbooks, each
   clearly marked as external practice not yet exercised in the
   maintainer's own projects. SMOTE and missing-value indicators stay
   out per the stronger prior in-house evidence.

Drafting proceeds as a separate build task against these decisions:
six files under `skills/exploring-reproducibly/` (four topic playbooks,
the generic base, the stat-test appendix), wired into `SKILL.md`'s
conditional-load list.
