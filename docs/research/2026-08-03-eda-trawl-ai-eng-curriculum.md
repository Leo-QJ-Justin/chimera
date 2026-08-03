# EDA Trawl — AI Engineering from Scratch curriculum (external cross-check)

> Research artifact for chimera. Mined 2026-08-03, Pass 3 of the EDA trawl.
> Purpose: use a third-party 503-lesson curriculum as an external completeness
> check for the maintainer's future per-topic EDA playbooks — what does it
> prescribe for data exploration/preparation that the maintainer's own notes
> and projects (Passes 1-2 of this trawl, and the prior pipeline-templates
> trawl in `docs/research/2026-07-30-pipeline-trawl-*.md`) do not already show
> evidence of.
>
> Source repo: `/home/leoqi/personal_projects/ai-engineering-from-scratch`,
> branch `my-exercises` (working tree only; no fetch, no checkout performed).
> All paths below are relative to that repo root.
>
> **External-content caveat.** This curriculum is third-party teaching
> material, not house style. Nothing here is a house convention by virtue of
> appearing in this document. Quotes are short and attributed to their lesson
> path; no lesson text is reproduced beyond what is needed to cite the claim.
> Every "candidate addition" is external input for the maintainer to accept,
> adapt, or reject at synthesis — not a recommendation this document makes on
> its own authority.

## 1. Scope and lesson selection

Per the trawl instructions, the EDA-relevant slice is: `phases/02-ml-
fundamentals/{08-feature-engineering, 09-model-evaluation (leakage/imbalance
diagnostics only), 15-time-series, 16-anomaly-detection, 17-imbalanced-data,
18-feature-selection}`, plus `01-what-is-machine-learning` for a dedicated
EDA/data-understanding section if one exists, plus the CV and NLP phases'
data-exploration/preparation lessons identified by name.

CV (`phases/04-computer-vision/`, 28 lessons) and NLP (`phases/05-nlp-
foundations-to-advanced/`, 29 lessons) titles were listed and screened by
name and by `##`/`###` header content for exploration/preparation/dataset-
analysis framing (see grep results below); no lesson in either phase is
titled as a dedicated EDA lesson. The closest matches by content are:

- **CV**: `01-image-fundamentals` ("Pixels, Channels, Color Spaces") —
  headers include "Step 1: Load an image and inspect its shape", "Step 2:
  Split channels and re-order layout", "Step 4: Normalize, standardize, and
  reverse it". This is the phase's data-understanding/preparation lesson;
  every later CV lesson assumes it.
- **NLP**: `01-text-processing` ("Tokenization, Stemming, Lemmatization") —
  the phase's text-preparation lesson; explicitly framed as "Language is
  continuous. Models are discrete. Preprocessing is the bridge."

No other CV or NLP lesson title or header set matched exploration/prep/
dataset-analysis framing strongly enough to include (a header-level grep for
`preprocess|prepar|explor|dataset|augment|normali[sz]|statistic|quality|
clean|inspect|distribution|imbalance|leakage|split|corpus` across both
phases' `docs/en.md` files returned only incidental hits — e.g. "Datasets you
will meet" in `12-video-understanding`, single-line advisories in `02-bag-of-
words-tfidf` and `03-word-embeddings-word2vec` about vocabulary size / OOV —
none rising to lesson-level EDA content). `glossary/terms.md` was checked for
EDA-specific terms (stationarity, data leakage, class imbalance, anomaly,
EDA/exploratory) and returned zero matches — the glossary does not define
EDA vocabulary as a first-class topic.

## 2. Per-lesson findings

### 2.1 `phases/02-ml-fundamentals/01-what-is-machine-learning/docs/en.md`

No dedicated EDA lesson exists this early in the curriculum; exploration is
folded into the workflow overview as one pipeline stage among several.

- The stated ML workflow (`Collect Data → Clean & Explore → Feature
  Engineering → Split Data → Train → Evaluate → Deploy → Monitor`) allots
  exploration one node: **"Clean & Explore: Handle missing values, remove
  duplicates, visualize distributions, spot anomalies. This step often takes
  60-80% of total project time."** (line 139). Topic: generic.
- The "When NOT to use ML" decision flowchart gates on data availability
  before any modeling choice — an EDA-adjacent go/no-go check, not a
  technique. Topic: generic.

### 2.2 `phases/02-ml-fundamentals/08-feature-engineering/docs/en.md`

The curriculum's most complete tabular-preparation lesson.

- Numerical transforms table: min-max, standardization, log transform
  ("compresses right-skewed distributions... turns multiplicative
  relationships into additive ones"), binning, polynomial features. Topic:
  tabular.
- Categorical encoding: one-hot, label, and **target encoding**, with an
  explicit leakage warning — **"Powerful but dangerous: high risk of data
  leakage. Must be computed only on training data and applied to test
  data."** (line 64). Topic: tabular.
- Missing-value strategies include an **indicator column**: "Add a binary
  column `was_this_missing` before imputing. The fact that data is missing
  can itself be informative" (line 85). Topic: tabular.
- Filter feature selection introduced here as EDA-adjacent triage:
  correlation, mutual information, variance threshold, with the summary
  **"A model with 10 good features will usually outperform a model with 10
  good features and 90 noisy ones"** (line 105). Topic: tabular.
- Text features (count vectorizer, TF-IDF) implemented from scratch. Topic:
  text/NLP.

### 2.3 `phases/02-ml-fundamentals/09-model-evaluation/docs/en.md`

Read only for EDA-adjacent diagnostics (leakage, target/class checks), not
evaluation methodology proper.

- **Data leakage taxonomy**: "fitting a scaler on the full dataset before
  splitting, including future data in time series prediction, using a
  feature that is derived from the target. Always split first, then
  preprocess" (line 135). Topic: generic.
- Class-imbalance recognition test used as a diagnostic, not a fix: the
  worked example shows a model that "always predicts negative" scoring 99%
  accuracy on a 99/1 split, framed as a check to run before trusting any
  accuracy number (lines 554-564 of the code walkthrough). Topic: tabular /
  count.
- Stratified k-fold is motivated as an EDA-driven decision: **"with
  imbalanced data, a random split might put very few minority samples in the
  validation fold, giving unstable estimates"** (line 141). Topic: tabular.

### 2.4 `phases/02-ml-fundamentals/15-time-series/docs/en.md`

The most detailed single-lesson EDA content found in Phase 2.

- **Stationarity check as a practical, code-first diagnostic**: rolling mean
  and rolling std over a window, plus a first/second-half mean and variance
  comparison, with the formal Augmented Dickey-Fuller test named but not
  implemented ("we do not implement ADF from scratch... the rolling
  statistics approach in our code gives a practical visual check", line
  108). Topic: time-series.
- **Autocorrelation/partial autocorrelation (ACF/PACF)** as the stated
  mechanism for choosing how many lag features to create: "Use lags up to
  where ACF becomes negligible" (line 143). Topic: time-series.
- **The target-alignment trap**, called "the most common bug in time series
  feature engineering": features must use values at t-1 or earlier, never t
  (line 145). Topic: time-series.
- Walk-forward validation (expanding vs. sliding window) presented as
  mandatory, with a worked "wrong vs. right" diagram contrasting random
  k-fold against temporal splits. Topic: time-series.
- Practical-tips section is explicitly EDA-first: **"Start with plotting.
  Before any modeling, plot the raw series. Look for trends, seasonality,
  outliers, structural breaks... A 30-second visual inspection often tells
  you more than an hour of automated analysis"** (line 414). Also: log-
  transform skewed series before lagging, hold out at least one full
  seasonal cycle, and watch for regime changes (pre/post-pandemic behavior
  shift). Topic: time-series.
- Baselines-before-modeling discipline: persistence, seasonal-naive, moving
  average, with the rule "If your fancy ML model loses to the seasonal naive
  baseline, you have a bug" (line 410). Topic: time-series.

### 2.5 `phases/02-ml-fundamentals/16-anomaly-detection/docs/en.md`

- Anomaly taxonomy (point / contextual / collective) as the framing for
  method choice. Topic: tabular.
- Method comparison table: Z-score, IQR, **Isolation Forest**, **Local
  Outlier Factor (LOF)** — assumptions, speed, high-dimensional handling,
  local-anomaly detection. Topic: tabular.
- Evaluation-under-imbalance guidance mirrors the imbalanced-data lesson:
  **"AUROC is misleading... Better metrics: Precision@k... AUPRC... and
  recall at a fixed false positive rate"** (lines 200-202). Topic: tabular /
  count.
- Production framing: threshold drift, alert fatigue, ensembling multiple
  detectors and flagging only points multiple methods agree on, feedback
  loops from human review back into the detector. Topic: generic.

### 2.6 `phases/02-ml-fundamentals/17-imbalanced-data/docs/en.md`

- Metrics-first framing: precision, recall, F1, **F-beta** ("F2 is common in
  fraud detection"), **AUPRC** ("a random classifier has AUPRC equal to the
  positive class rate, not 0.5 like ROC"), and **Matthews Correlation
  Coefficient**, with the worked always-negative example showing precision/
  recall/F1/MCC all correctly reading as zero. Topic: tabular / count.
- **SMOTE** implemented from scratch (k-NN interpolation between minority
  points), contrasted with random oversampling ("risks overfitting because
  the model sees identical points repeatedly") and random undersampling.
  Topic: tabular.
- Class weights, threshold tuning by sweeping 0.05-0.95 and maximizing a
  chosen metric on a validation split, and **explicit cost-sensitive
  learning** with a named cost matrix (C_FN vs. C_FP). Topic: tabular.
- Decision flowchart ties imbalance ratio (mild/moderate/severe) and dataset
  size to a specific strategy combination. Topic: tabular.

### 2.7 `phases/02-ml-fundamentals/18-feature-selection/docs/en.md`

- Three-way taxonomy — filter / wrapper / embedded — used as the lesson's
  organizing structure. Topic: tabular.
- **Mutual information**, stated as capturing what correlation misses: **"A
  feature might have zero correlation with the target but high mutual
  information because the relationship is quadratic or periodic"** (line
  85), with a binning-count caveat (too few bins loses information, too many
  adds noise). Topic: tabular.
- **Recursive Feature Elimination (RFE)** and **L1/Lasso** as wrapper vs.
  embedded alternatives, with an explicit cost note: "With 500 features and
  a target of 10, that is 490 training runs" (line 119). Topic: tabular.
- **Permutation importance**, framed as a bias-correction for tree
  importance: **"tree-based importance is biased toward features with many
  unique values (high cardinality). A random ID column will appear important
  because it perfectly splits every sample. Use permutation importance as a
  sanity check"** (line 153). Topic: tabular.

### 2.8 `phases/04-computer-vision/01-image-fundamentals/docs/en.md`

The CV phase's foundational data-understanding lesson; framed entirely
around silent-failure prevention in preprocessing.

- The stated failure mode motivating the whole lesson: **"Pass a `uint8`
  image where the model wants `float32` and it will still run — and silently
  produce garbage... None of this throws an error. It just ruins your
  metrics"** (line 19). Topic: images.
- A three-row byte-range/dtype table (raw `uint8` [0,255], normalized
  `float32` [0,1], standardized `float32` roughly [-2,+2]) framed as the
  three states every image tensor passes through, with the claim that
  feeding raw uint8 to a standardized-input model is **"the single most
  common silent failure in applied vision"** (line 147). Topic: images.
- Layout inspection (HWC vs. CHW) and channel splitting as the first "Build
  It" step — literally `arr.shape`, `arr.dtype`, `arr.min()`/`arr.max()`,
  per-channel means — the image analogue of `df.info()`/`df.describe()`.
  Topic: images.
- Color-space conversion (RGB → grayscale, HSV) motivated by task fit rather
  than shown as universally correct: "For most modern CNNs you feed RGB. You
  meet other spaces when..." with a three-case table (HSV for classical
  CV/segmentation, YCbCr for JPEG/video internals, grayscale for OCR).
  Topic: images.
- Resize/interpolation method table (nearest/bilinear/bicubic/Lanczos) with
  a stated rule of thumb: "bilinear for training, bicubic or lanczos for
  assets you will look at, nearest for anything containing integer class
  IDs" (line 197). Topic: images.
- The lesson ships a reusable diagnostic prompt/skill pair: `outputs/prompt-
  vision-preprocessing-audit.md` ("turns any model card or dataset card into
  a checklist of the exact preprocessing invariants") and `outputs/skill-
  image-tensor-inspector.md` ("given any image-shaped tensor or array,
  reports dtype, layout, range, and whether it looks raw, normalized, or
  standardized"). Topic: images.

### 2.9 `phases/05-nlp-foundations-to-advanced/01-text-processing/docs/en.md`

The NLP phase's foundational text-preparation lesson.

- Tokenization/stemming/lemmatization implemented from scratch with explicit
  failure modes named per technique (e.g. Porter stemmer's `ies -> i` rule:
  **"ponies -> poni, not pony"**, line 80). Topic: text/NLP.
- Two production-preparation caveats not seen elsewhere in this trawl:
  - **Reproducibility drift**: "NLTK and spaCy change tokenization and
    lemmatizer behavior between versions... Pin library versions in
    `requirements.txt`. Write a preprocessing regression test that freezes
    expected tokenization of 20 sample sentences. Run it on every upgrade"
    (line 209). Topic: text/NLP.
  - **Train/inference preprocessing mismatch**, called "the single most
    common production NLP failure": "If you preprocess during training, you
    must run the identical function during inference. Ship preprocessing as
    a function inside the model package, not as a notebook cell the serving
    team rewrites" (line 211). Topic: text/NLP.
- Adjacent, brief: `02-bag-of-words-tfidf/docs/en.md` line 232 advises to
  **"Refuse to recommend embeddings when the user has under 500 labeled
  examples... Flag class imbalance as needing more than a vectorizer
  change"** — a one-line EDA-adjacent guardrail, not a full technique.
  Topic: text/NLP.

## 3. Maintainer-authored exercise deltas on `my-exercises`

None of the nine lessons read for this pass have maintainer exercise work.

`git rev-list --left-right --count origin/main...my-exercises` returns `0
0` — the `my-exercises` branch has zero commits ahead of (or behind)
`origin/main`; no exercise work has been committed to this branch at all.
The only maintainer activity in the working tree at the time of this trawl is
two uncommitted modifications (`git status --short`):

```
 M phases/14-agent-engineering/01-the-agent-loop/code/main.py
 M phases/14-agent-engineering/01-the-agent-loop/docs/en.md
```

Both are in Phase 14 (agent engineering), outside this trawl's EDA-relevant
scope (Phase 2 ML fundamentals, Phase 4 computer vision, Phase 5 NLP). **No
maintainer-authored exercise deltas touch the EDA slice covered by this
pass** — every finding above is upstream lesson content, not practiced work,
and is weighted accordingly (external reference only, not evidence of the
maintainer having exercised the technique).

## 4. External coverage by topic

| Topic | Lessons providing evidence | Depth |
|---|---|---|
| Tabular | `08-feature-engineering`, `09-model-evaluation`, `16-anomaly-detection`, `17-imbalanced-data`, `18-feature-selection` | Deep — five lessons, from-scratch implementations for every technique, decision flowcharts per lesson |
| Count (imbalance/rare-event diagnostics) | `09-model-evaluation`, `16-anomaly-detection`, `17-imbalanced-data` | Deep — metrics (AUPRC, MCC, Precision@k), sampling, cost-sensitive framing all cross-referenced across three lessons |
| Time-series | `15-time-series` | Deep — stationarity, ACF/PACF, walk-forward, baselines, all in one lesson with a dedicated practical-tips section |
| Geospatial | none found | None — no lesson in the trawled scope addresses spatial data; not covered by this curriculum's EDA-relevant slice at all |
| Text/NLP | `01-text-processing`, `08-feature-engineering` (TF-IDF), `02-bag-of-words-tfidf` (one-line guardrail) | Moderate — one dedicated preparation lesson plus incidental coverage in the tabular feature-engineering lesson |
| Images | `01-image-fundamentals` | Moderate — one dedicated lesson, tightly scoped to pixel/tensor/dtype/layout hygiene rather than dataset-level exploration (no class-balance, resolution-distribution, or corrupted-image-detection content found) |
| Audio | none found | None — no audio phase or lesson exists in this curriculum's directory structure |
| Generic | `01-what-is-machine-learning`, `09-model-evaluation`, `16-anomaly-detection` | Shallow — workflow-level framing ("Clean & Explore," leakage-first-not-last) rather than technique depth |

## 5. Candidate additions

External techniques the curriculum prescribes that do not appear (by grep,
across `docs/research/2026-07-30-pipeline-trawl-*.md` and
`2026-07-30-analysis-style-*.md`) in the maintainer's own trawled project
corpus. The maintainer's Atlas vault reportedly has its own `Exploratory &
Preparation/` notes per topic (per `docs/specs/2026-07-30-pipeline-
templates-trawl-plan.md`, line 141-142) — those notes were explicitly out of
scope for the pipeline trawl and were not read for this pass either; absence
here means "not attested in the project-code corpus reviewed so far," not
"absent from every note the maintainer has ever written." Each item below is
external reference only; adoption is a synthesis decision.

1. **Rolling-window stationarity check + ACF/PACF-driven lag selection**
   (`15-time-series`). Not attested in the trawled corpus outside the
   already-known walk-forward requirement (USEP spec, via the Atlas trawl).
   Candidate for playbook: yes — this is a concrete, cheap diagnostic
   (`rolling_mean`, `rolling_std`, a first/second-half comparison) that
   slots directly into a time-series EDA playbook's "before you difference
   or lag anything" step.

2. **Isolation Forest / Local Outlier Factor as anomaly-detection methods
   beyond Z-score** (`16-anomaly-detection`). The one anomaly-detection
   technique attested in the maintainer's corpus is per-group Z-score
   (Sembcorp cleaning pipeline, `2026-07-30-pipeline-trawl-sembcorp.md`,
   line 291). No multivariate or density-based method appears. Candidate for
   playbook: yes — Z-score is univariate only; the curriculum's own
   comparison table states Z-score "fails on multimodal distributions,"
   which is exactly the gap Isolation Forest/LOF close.

3. **Precision@k / AUPRC as the reporting metric for anomaly and rare-event
   detection**, replacing accuracy/AUROC (`16-anomaly-detection`,
   `17-imbalanced-data`). Not attested; the maintainer's corpus references
   macro-F1 as the primary metric (Micron) but not AUPRC or Precision@k
   specifically. Candidate for playbook: yes — directly composable with the
   Z-score-only anomaly work already in production.

4. **Mutual information as a nonlinear-relationship filter**, distinct from
   correlation (`08-feature-engineering`, `18-feature-selection`). Not
   attested. Candidate for playbook: yes — cheap, model-free, and the
   curriculum's own framing ("captures relationships correlation misses")
   is a natural complement to a correlation-matrix EDA step that likely
   already exists in the maintainer's own tabular EDA notebooks.

5. **Permutation importance as a cardinality-bias correction for tree
   importance** (`18-feature-selection`). Not attested. Candidate for
   playbook: yes, but flagged as evaluation-adjacent rather than pure EDA —
   it needs a fitted model, so it belongs at the boundary between an EDA
   playbook and a model-diagnostics playbook. Include with that caveat
   noted.

6. **Recursive Feature Elimination (RFE) and variance threshold as an
   explicit filter → wrapper pipeline** (`18-feature-selection`). Not
   attested. Candidate for playbook: partial — variance threshold is trivial
   and worth a one-line mention; RFE is compute-heavy ("490 training runs"
   in the curriculum's own worked example) and may not fit an EDA-stage
   playbook versus a modeling-stage one.

7. **Matthews Correlation Coefficient (MCC) for imbalanced-classification
   diagnosis** (`17-imbalanced-data`). Not attested; the maintainer's
   corpus uses macro-F1. Candidate for playbook: yes — MCC is a single
   number that is "high score only when the model does well on both
   classes," a useful complement to macro-F1 for a diagnostics checklist,
   cheap to compute alongside existing metrics.

8. **Explicit cost-matrix framing for threshold selection**
   (`17-imbalanced-data`). The maintainer's corpus has strategy-switch
   constants (e.g. `SMOTE_RATIO`) and documented reject decisions but no
   named cost matrix (`C_FN`, `C_FP`) tying threshold choice to a stated
   business cost ratio. Candidate for playbook: partial — the concept (cost-
   aware thresholding) likely already exists informally; the curriculum's
   contribution is making the matrix explicit and auditable, which is a
   documentation practice more than a new technique.

9. **SMOTE.** Not a candidate addition — the maintainer's corpus already
   contains a fuller treatment than this curriculum lesson: SMOTE was
   implemented, A/B tested through the project's own CV harness, and
   explicitly rejected with a documented rationale ("fabricating synthetic
   minority points from as few as 23 real samples," `2026-07-30-analysis-
   style-micron.md`, lines 98-101). Candidate for playbook: no — the
   maintainer's own prior work is stronger evidence than the curriculum's
   from-scratch implementation; if anything, the curriculum should defer to
   the maintainer's rejection rationale, not the reverse.

10. **Missing-value indicator column.** Not a candidate addition — already
    practiced (`feat_80_is_missing` in the Micron project, `2026-07-30-
    analysis-style-micron.md`, lines 81-83), and the maintainer's version
    ties the indicator to a specific EDA finding (missingness correlated
    with a specific class) rather than applying it generically. Candidate
    for playbook: no.

11. **Leave-one-out / smoothed target encoding as a named leakage-safe
    variant.** Leakage discipline itself is a strong, repeatedly-attested
    house habit (stateless `clean()` pre-split vs. stateful `fit_transform`/
    `transform` train-only, `2026-07-30-pipeline-trawl-micron.md`, "Leakage
    as architecture," lines 107+). The specific smoothed target-encoding
    formula (`08-feature-engineering`) is not attested. Candidate for
    playbook: partial — worth a one-line technique reference under an
    existing "leakage-safe encoding" heading rather than a new section.

12. **NLP reproducibility-drift and train/inference-mismatch discipline**
    (`01-text-processing`: pin library versions, freeze a tokenization
    regression test, ship preprocessing as a packaged function). Not
    attested anywhere in the maintainer's trawled corpus, which is entirely
    tabular/time-series project work with no NLP pipeline reviewed to date.
    Candidate for playbook: yes — this is a text/NLP-specific engineering
    discipline with no tabular analogue already covered, and it directly
    addresses a production failure mode ("the single most common production
    NLP failure") the curriculum names explicitly.

13. **Image-tensor preprocessing-invariant audit** (`01-image-fundamentals`:
    dtype/layout/range inspection as the first move on any image dataset,
    plus the shipped `skill-image-tensor-inspector` and `prompt-vision-
    preprocessing-audit`). Not attested in the project corpus this pass
    grepped; Pass 2 of this trawl (run in parallel,
    `2026-08-03-eda-trawl-all-assignments.md`, A5P1) later surfaced
    single-image shape/dtype/mode inspection at coursework level, so the
    habit is partially attested but not the systematic audit. Candidate
    for playbook: yes — it is the vision analogue of the already-standard
    `df.info()`/`df.describe()` habit, and the curriculum's explicit
    raw/normalized/standardized range table sharpens what the coursework
    only gestures at.

14. **Class-distribution / resolution-distribution / corrupted-image
    dataset-level EDA for images.** Absent from this curriculum —
    `01-image-fundamentals` covers single-image tensor hygiene only, not
    dataset-level image EDA (no class balance, no resolution-histogram,
    no duplicate/corrupt-file detection anywhere in the CV phase's
    screened headers). Candidate for playbook: no addition to make here —
    a **gap in the external source itself**. The parallel passes of this
    trawl show the house corpus supplies it amply: the vault's
    `EDA for Images` note (Pass 1) and the coursework's A5P2 image EDA
    (Pass 2) both cover class balance, resolution/aspect-ratio scans, and
    corrupt-file detection, so an images playbook would draw on those and
    owe nothing to this curriculum for dataset-level content.
