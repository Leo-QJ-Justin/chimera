# EDA Trawl — Atlas vault (stated best practices)

> Research artifact for chimera. Mined 2026-08-03 (Pass 1 of the approved
> EDA-playbooks research trawl). Source: the maintainer's Obsidian vault
> (read-only; nothing written, nothing modified). Role: mine the vault for
> EDA technique content that will later feed per-topic EDA playbooks
> (candidate topics: tabular, count, time-series, geospatial, text/NLP).
> Register matches `docs/research/2026-07-30-pipeline-trawl-atlas.md` —
> evidence-first, file paths as citations, verbatim prescriptions quoted
> short, honest grading including anti-patterns and dead notes. All paths
> relative to `00 Notes/` in the vault root
> (`/mnt/c/Users/leoqi/Desktop/Atlas/00 Notes/`).

## Primary notes — `ML Methods & Workflow/Exploratory & Preparation/`

## 1. Exploratory Data Analysis

Path: `Exploratory & Preparation/Exploratory Data Analysis.md` (478 lines).
The generic, un-typed EDA note — every example uses a tabular HDB
resale-flat dataset, but nothing in the note gates on data type.

**Stated order, five numbered stages:**

1. **Preliminary Data Exploration** — load → `df.head()` → `df.info()` →
   `df.isna().sum()` → `df.describe().T` → `df.duplicated().sum()` → view
   duplicated rows (`df[df.duplicated(keep=False)].sort_values(...)`) →
   `df.drop_duplicates(inplace=True)`.
2. **Univariate Analysis** — bar charts (`sns.countplot`) for categorical,
   histograms (`sns.histplot(..., kde=True)`) for continuous, line charts
   for counts-over-time. Bar-chart annotation pattern given in full
   (`count_plot.annotate(...)` looping `.patches`).
3. **Bivariate Analysis** — boxplots (category vs continuous), subplot bar
   charts (two categoricals side by side, sorted by count), scatter plots
   (two continuous, hue by a third categorical).
4. **Outlier Analysis** — ad hoc boolean-mask filtering on already-known
   suspicious combinations (`df[(df['flat_type']=='3 ROOM') &
   (df['floor_area_sqm']>150) & ...]`), not a general detection method.
5. **Correlation Analysis** — Pearson vs Spearman, each with formula,
   worked heatmap code, and an explicit **limitations list**: Pearson
   assumes continuous + linear + normal + homoscedastic and is
   outlier-sensitive; Spearman only needs monotonic + ordinal/interval/
   ratio, is rank-based (loses magnitude information, sensitive to ties),
   and *underrepresents* meaningful outliers/skew precisely because it is
   robust to them.

Verbatim: *"EDA involves examining datasets to summarize their main
characteristics, often using visualization techniques."* Stated importance
bullets: Data Quality Check (missing values, duplicates, outliers),
Uncover Patterns, Hypothesis Generation, Feature Selection, Data
Visualization.

**Tags:** generic, tabular, count (bar-chart/countplot usage is explicitly
the count-data path).

Candidate for playbook: **yes** — this is the closest thing the vault has
to a generic EDA spine (preliminary → univariate → bivariate → outlier →
correlation) and should seed the shared/generic playbook section that
per-topic playbooks extend. The five-stage order and the Pearson/Spearman
limitations table are worth lifting near-verbatim.

## 2. EDA for Images

Path: `Exploratory & Preparation/EDA for Images.md` (476 lines). Fully
image-typed, six numbered sections, each with **Purpose** →
**Implementation** → **Interpretation** structure (distinct from the
generic note's plain numbered list).

1. **Loading Image Metadata** — iterate `DATA_DIR.rglob("*")`, filter by
   extension set, `Image.open(p)` + `im.load()` (forces load to catch
   truncated files), catch `(UnidentifiedImageError, OSError, ValueError)`
   into a `bad` list, build a DataFrame of `path, label, width, height,
   area, aspect ratio, mode`. Verbatim: *"Instead of loading all images
   into memory, we iterate through the files and extract key
   properties."*
2. **Class Distribution** — `value_counts()`, bar chart with mean-count
   reference line, `imbalance_ratio = max_count / min_count`. Worked
   example calls a **2.67 ratio "moderate but significant"** and
   prescribes three responses: stratified split, aggressive augmentation
   on minority classes, weighted loss/sampler.
3. **Resolution & Aspect Ratio** — `describe()` on width/height/area/aspect
   ratio, 2×2 histogram grid, width-vs-height scatter colored by aspect
   ratio. Findings drive transform choice: high dimension variance →
   `Resize`; high aspect-ratio variance → `CenterCrop`/`RandomResizedCrop`
   over naive square resize (avoids distortion).
4. **Format & Color Mode** — extension counts and PIL `mode` counts; rule:
   **force all images to RGB** (`img.convert('RGB')`) because pretrained
   models expect 3-channel input; flags `RGBA`/`P`/`CMYK` as risks.
5. **Qualitative sample grid + saliency overlay** — Sobel-gradient
   magnitude heatmap over a 4×4 random sample grid, used to justify
   augmentation choices (safe: `RandomHorizontalFlip`, `ColorJitter`;
   avoid: `RandomVerticalFlip` for food imagery specifically).
6. **Advanced Physical Attributes** — **Laplacian variance** for
   blurriness (low variance → blurry), **HSV saturation mean**, **HSV
   value-channel std** for contrast; P5/P95 percentile reporting;
   filter-function factories (`filter_laplacian`, `filter_saturation`,
   `filter_contrast`, `invert`) for targeted inspection of outlier images.

**Tags:** images.

Candidate for playbook: **yes** — the single most complete, self-contained
per-topic EDA guide in the vault. Directly transplantable: metadata-table
construction, class-imbalance-ratio check, resolution/aspect-ratio
diagnostics driving transform choice, forced-RGB rule, and the
blur/saturation/contrast percentile-filter utilities.

## 3. EDA for NLP

Path: `Exploratory & Preparation/EDA for NLP.md` (309 lines). Fully
text-typed, 11 numbered sections plus a closing 8-step workflow-integration
list (§12).

1. **Corpus Definition** — defines corpus as tokenization/vocabulary
   boundary; subsets by label/source/domain enable drift comparison.
2. **Text Preprocessing** — table of 9 cleaning functions (remove HTML,
   lowercase, standardize accents, remove URLs, expand contractions,
   remove mentions/hashtags, remove digits, remove special characters,
   remove punctuation) each with a stated rationale column. Verbatim
   caveat on the last: *"Should be tested before removal — punctuation
   carries sentiment information."*
3. **Language Detection** — `langdetect` with `DetectorFactory.seed = 0`
   for reproducibility, filter to `df["language"] == "en"`, visualize
   distribution. Verbatim rationale: *"Prevents contamination by foreign
   or mixed-language documents that distort metrics and tokenization."*
4. **Tokenization and Document Metrics** — `nltk.word_tokenize`, per-doc
   token count / vocab size / type-token ratio (TTR).
5. **Vocabulary and Length Metrics** — character count (truncation
   detection), token count, vocab size, TTR, log-TTR/MTLD as
   length-bias-adjusted alternatives, frequency cutoffs for subword
   modeling.
6. **Corpus Summary Visualization** — total tokens, vocab size, top-10
   words, three-panel histplot (token count / vocab size / TTR) split by
   label.
7. **Word Cloud Visualization** — `WordCloud`, used "to verify cleaning
   and compare dominant tokens across labels."
8. **Sentiment Analysis** — `TextBlob` polarity vs text-length scatter,
   hue by label.
9. **Label–Sentiment Comparison** — comparison table distinguishing
   human-annotated label (categorical, ground truth) from computed
   sentiment (continuous, noise-detection use); worked mismatch example
   ("Not bad at all." labeled negative, sentiment +0.3) to catch
   mislabeling.
10. **Punctuation/Capitalization as Sentiment Intensifiers** —
    `sentiment_intensity_features()` returning exclamation count, question
    count, capital ratio, punctuation density; framed as *magnitude*
    features distinct from polarity.
11. **Polarity vs Strength** — conceptual distinction table (direction vs
    magnitude of sentiment).
12. **Workflow Integration** — 8-step order: clean/normalize → detect &
    filter language → tokenize & compute lexical metrics → quantify
    vocabulary/diversity → visualize corpus distributions → analyze
    sentiment → compare sentiment to labels → retain
    punctuation/capitalization for magnitude when relevant.

**Tags:** text/NLP.

Candidate for playbook: **yes** — second-most complete per-topic guide.
The preprocessing-function table, language-detection-as-filter step, TTR/
vocabulary-size metrics, and the label-vs-sentiment mismatch check are all
directly liftable; the 12-section order is the stated canonical sequence.

## 4. Data Cleaning

Path: `Exploratory & Preparation/Data Cleaning.md` (155 lines). Two
concatenated parts: an unordered "Critical Steps" bullet essay, then a
numbered **"General Data Cleaning Workflow"** (8 steps) that is the
operative content.

**8-step workflow, verbatim headers:**

1. Understand the Data — load & inspect (`.head()`, shape, `.info()`,
   `.describe()`), check data dictionary, identify expected
   ranges/formats/units.
2. Standardize Structure — rename columns, set correct dtypes, encoding
   consistency, normalize units.
3. Handle Missing Data — `.isna().sum()`, treat placeholder values (`'NA'`,
   `'-999'`, `'?'`) as missing, decide drop/impute/keep-as-NaN.
4. Remove or Flag Duplicates — exact via `.drop_duplicates()`, near
   duplicates decided case-by-case.
5. Handle Irrelevant Data — drop irrelevant columns, filter irrelevant
   rows.
6. Correct Inconsistent/Erroneous Data — standardize categorical value
   spellings, fix typos, check value ranges, validate cross-field
   relationships (`start_date <= end_date`).
7. Outlier Detection & Treatment — IQR / z-score / domain rules; treat by
   context (correct if error, keep if genuine, cap/winsorize for
   modeling).
8. Final Consistency Checks — confirm no unexpected missing/placeholder
   values remain, re-check dtypes/formats, save a clean copy, **keep a log
   of cleaning steps for reproducibility**.

**Leakage rule worth lifting verbatim** (from the unordered preamble,
under "Removing Unnecessary data"): *"Dropping Post-hoc Features:
Removing columns that will not be available at the time of prediction...
Including them in the model would be like using information from the
future... Removing such features will prevent data leakage and ensure the
model's performance is realistic and reliable."* Also: *"dropping data
should always be the last resort"* and *"Always investigate if missing
values can be imputed by inferring from other columns."*

**Tags:** generic.

Candidate for playbook: **yes** — the 8-step cleaning workflow is the
generic data-quality checklist every topic playbook's "clean before you
plot" section should cite; the leakage/post-hoc-feature warning and the
"log your cleaning steps" rule are cross-cutting and worth quoting
verbatim in the generic playbook.

## 5. Data Cleaning & Preprocessing

Path: `Exploratory & Preparation/Data Cleaning & Preprocessing.md` (33
lines). Self-marked dead note. Verbatim first line: *"⚠️ Superseded. This
was a small workflow-index note. The substantive content lives in [[Data
Cleaning]]; the full prep workflow is mapped in [[Exploratory &
Preparation]]. Safe to delete."* Remaining body is a bare link list
(Data Cleaning, Feature Engineering, Data Splitting & Scaling, Feature
Encoding) with no prose beyond "Putting it all together in pipelines."

**Tags:** generic (meta, superseded).

Candidate for playbook: **no** — explicitly superseded by the maintainer;
mining it further would duplicate note 4. Recorded here only because it
was on the required-read list.

## 6. Data Splitting & Scaling

Path: `Exploratory & Preparation/Data Splitting & Scaling.md` (300 lines).
Downstream-of-EDA preprocessing note, not an EDA technique catalog itself,
but it encodes decision rules that gate on EDA findings.

- **Feature-target separation** — `X = df.drop(columns=target)`, `y =
  df[target]`.
- **Train/val/test ratios**: train 60-80%, val 10-20%, test 10-20%;
  two-stage `train_test_split` (80/20 then 50/50 on the remainder) with
  `random_state=42` hardcoded both times.
- **Stratified splitting** — worked numeric example (100 samples,
  50/30/20 class split) showing how an unstratified 70/30 split can
  distort test-set proportions to 33/33/33; `stratify=y` on both split
  calls for classification.
- **Split-then-scale rule, stated as a hard invariant**: *"NOTE: We split
  then scale, scaling is done AFTER splitting your data into training,
  validation and test set."* Rationale given in full: fitting a scaler
  before splitting leaks validation/test statistics (mean, std, min, max)
  into training, producing "overly optimistic performance estimates."
- **Normalization vs Standardization** — Min-Max to [0,1] vs zero-mean/
  unit-variance; normalization is outlier-sensitive and unnecessary for
  tree-based models; standardization assumes/benefits distance-based and
  gradient-descent-optimized algorithms, also unnecessary for trees.

**Tags:** generic, tabular.

Candidate for playbook: **partial** — the split-then-scale leakage rule
and the stratification rationale belong in the generic playbook as a
"what EDA must decide before splitting" callout (class balance from EDA
→ stratify decision), but the split-ratio and scaler-selection content
itself is pipeline construction, not an EDA step.

## 7. Feature Encoding

Path: `Exploratory & Preparation/Feature Encoding.md` (114 lines).
One-hot vs ordinal encoding: definitions, worked color/size examples,
drawback lists (one-hot: high dimensionality → overfitting risk, proposed
fixes "feature hashing?" and "aggregating into smaller categories";
ordinal: imposed order and unequal spacing assumption, risk of model
misinterpreting distances). Closing code block builds a full
`ColumnTransformer` (numerical/nominal/ordinal/passthrough) — identical to
the block in note 11 (Pipelines.md).

**Tags:** tabular.

Candidate for playbook: **partial** — encoding mechanics are pipeline
construction, not EDA; but the underlying question the note never states
explicitly (cardinality count per categorical column, is there a natural
order) is exactly what an EDA step must surface to make the one-hot-vs-
ordinal decision. Worth a pointer, not a lift.

## 8. Feature Engineering

Path: `Exploratory & Preparation/Feature Engineering.md` (7 lines). A
bare branch-level index stub: *"Branch-level overview. Sub-topics:"*
followed by three wikilinks (`Discussion- Creating Boolean Flags`,
`Feature Encoding`, `Feature Importance`) and a stray trailing `S` with no
attached content — looks like an interrupted edit. `Feature Importance.md`
was not on the required-read list and was not separately fetched.

**Tags:** generic (meta, stub).

Candidate for playbook: **no** — no technique content, just a broken
index page.

## 9. Imbalanced Data

Path: `Exploratory & Preparation/Imbalanced Data.md` (651 lines, the
longest primary note). Split between an EDA-relevant diagnostic
(§imbalance table) and modeling responses (resampling, loss functions)
that are downstream of EDA.

**Imbalance-degree table** (the EDA-relevant part), verbatim:

| Degree of Imbalance | Proportion of Minority Class |
|---|---|
| Mild | 20-40% of the data set |
| Moderate | 1-20% of the data set |
| Extreme | <1% of the data set |

Stated as guideline, not rigid rule. Everything downstream of this
classification is a modeling response, not an EDA step: Random
Oversampling / Undersampling / combination (all with worked stratified-
split-then-resample code, and the explicit warning **"Do not resample the
test set; it should remain untouched"**), SMOTE (with the caveat that
synthetic interpolation "might create some unrealistic combinations of
features"), Precision-Recall curve as the diagnostic to prefer over
ROC-AUC under imbalance (*"The ROC curve... can be misleading when there
is a large class imbalance, as it includes true negatives in its
calculation"*), class weighting (formulas for multi-class inverse
frequency and PyTorch `pos_weight`), label smoothing, and a full Focal
Loss PyTorch implementation.

**Tags:** count, tabular (the imbalance table); the rest is modeling, not
EDA-tagged.

Candidate for playbook: **partial** — the imbalance-degree table is a
direct fit for the tabular/count playbooks' "check target distribution"
step (mild/moderate/extreme thresholds); the Precision-Recall-over-ROC
rule is a useful "which plot to reach for once you know you're
imbalanced" note. Resampling code, class weighting, label smoothing, and
Focal Loss belong in a modeling or training-skeleton note, not an EDA
playbook.

## 10. Discussion- Creating Boolean Flags

Path: `Exploratory & Preparation/Discussion- Creating Boolean Flags.md`
(89 lines). A worked case study, not a general checklist: town-name
one-hot encoding vs a derived `mature_estate` boolean flag for HDB resale
data.

Key content: dummy-variable-trap note (one dummy dropped automatically);
pros/cons of full one-hot (captures location effects vs 26→25 dummy
columns, overfit risk, poor generalization to unseen towns) vs the
boolean flag (interpretable "mature estate premium," dimensionality
reduction, but loses town-specific granularity); a **multicollinearity
warning specific to classical regression** — the flag is a linear
combination of the town dummies it was derived from, so including both
destabilizes OLS/logistic coefficients even after dropping one dummy;
tree/NN models are stated to tolerate the redundancy (flag acts as an
early-split shortcut feature) at some interpretability cost. Closing
"when to use which" table: town dummies when data is sufficient and
model is flexible; flag when simplicity/interpretability/limited-data
generalization matter; both only in non-linear ML models if performance
justifies it.

**Tags:** tabular.

Candidate for playbook: **partial** — a good illustrative case study for
a tabular playbook's cardinality-reduction section, but it is a single
worked example tied to one dataset, not a general technique or checklist
to lift verbatim.

## 11. Pipelines

Path: `Exploratory & Preparation/Pipelines.md` (72 lines). One-paragraph
rationale for `sklearn.pipeline.Pipeline` (*"automate and encapsulate
multiple steps into one coherent process"*) followed by the **identical**
`ColumnTransformer` code block already present in note 7 (Feature
Encoding.md) — numerical/nominal/ordinal/passthrough composition,
`remainder='passthrough'`, `n_jobs=-1`. No new content beyond the intro
sentence; ends with an empty "Reference material / Links" stub.

**Tags:** generic (pipeline mechanics, not EDA).

Candidate for playbook: **no** — pure duplicate of note 7's code, and
pipeline construction is downstream of EDA, not an EDA technique. Flagged
as a within-vault duplication the maintainer may want to resolve (delete
one, link the other) independent of the playbook work.

---

## Secondary pass

### Statistical Inference — `ML Methods & Workflow/Statistical Inference/`

Lighter pass, EDA-relevant content only: the decision rules for **which
significance test to run**, since choosing and running that test is
itself an EDA action once distribution/normality has been established.

**`Statistical Inference — Hypothesis Testing.md`** (78 lines) is the hub.
Its decision tree is the single most reusable artifact in this cluster,
given verbatim as a fenced block:

```
Is your outcome variable continuous or categorical?
│
├── Categorical → Chi-Square Tests guide
│
└── Continuous → How many groups are you comparing?
    │
    ├── One group vs a known value
    │   ├── Normal + large n + known σ → Z-test
    │   ├── Normal + small n or unknown σ → One-sample t-test
    │   └── Non-normal or small n → Sign test / Wilcoxon signed-rank
    │
    ├── Two independent groups
    │   ├── Normal + large n + known σ → Two-sample Z-test
    │   ├── Normal + equal variances → Pooled t-test
    │   ├── Normal + unequal variances → Welch's t-test
    │   └── Non-normal → Mann-Whitney U test
    │
    └── Same group, two time points (paired)
        ├── Normal → Paired t-test
        └── Non-normal → Wilcoxon signed-rank test
```

Plus a directional check (one-sided vs two-sided, decided *before* seeing
data) and "The Three Questions to Always Ask First": what am I comparing,
is my data approximately normal (QQ plot or CLT-by-sample-size), do I
know the population variance (almost always no → t over Z in practice).

**`Parametric Tests — Z-test & T-test.md`** (242 lines) operationalizes
the tree: structure decision (paired / independent two-sample /
one-sample) crossed with direction decision (one/two-sided) = six
combinations; **Levene's test before Pooled-vs-Welch** (`p > 0.05` → equal
variances → Pooled; `p < 0.05` → Welch, stated as "the safer default if
you're unsure"); proportions Z-test via
`statsmodels.stats.proportion.proportions_ztest`.

**`Non-Parametric Tests — Wilcoxon, Mann-Whitney & Sign Test.md`** (115
lines) gives the **normality-check-first rule**: Shapiro-Wilk (`p > 0.05`
→ parametric OK, `p < 0.05` → consider non-parametric) plus a QQ plot,
then a parametric-equivalent mapping table (Sign↔one-sample t, Wilcoxon
signed-rank↔paired t, Mann-Whitney U↔independent two-sample t).

**`Chi-Square Tests & Categorical Data.md`** (85 lines) splits by variable
count: Goodness-of-Fit (one categorical vs a hypothesized distribution)
vs Test of Independence (two categorical, contingency table,
`chi2_contingency`), plus Cramer's V as the associated effect size.

**`ANOVA & Post-Hoc Tests — One-Way, Two-Way & Tukey-Kramer.md`** (156
lines) extends to 3+ groups: assumption checklist (independence,
normality via Shapiro-Wilk, homogeneity of variance via Levene's) gating
one-way ANOVA vs its non-parametric fallback **Kruskal-Wallis**;
Tukey-Kramer as the stated default post-hoc test for unequal group sizes
over Bonferroni ("overly strict and has lower power").

**Tags:** generic (the decision framework applies across tabular, count,
and any topic with a group-comparison EDA question); the specific tests
skew tabular/count.

Candidate for playbook: **yes** — the "which test" decision tree plus its
Shapiro-Wilk/Levene's gating checks is exactly the kind of decision-support
content an EDA playbook needs when a maintainer asks "is this difference
real." It should be summarized (not reproduced in full) as a
generic-playbook decision aid, with the tree quoted verbatim since it is
short and precise.

### Time Series & Econometrics — `ML Methods & Workflow/Time Series & Econometrics/`

Lighter pass, EDA-relevant content only (stationarity, decomposition,
ACF/PACF, outliers) — excluded the modeling-family notes (ARIMA, VAR,
GARCH internals) as out of EDA scope.

**`Time Series Forecasting — Complete Workflow & Reference.md`** (261
lines, the cluster hub) frames the two EDA-relevant steps inside a
13-step workflow table: **Step 1 Data Preparation** (clean, transform,
visualize) and **Step 2 Stationarity Check** (ADF/KPSS, difference or
transform as needed). Everything from Step 3 onward (model selection,
fitting, residual/volatility diagnostics) is modeling, not EDA, though the
diagnostic *plotting mechanics* (`plot_acf`, `plot_pacf`) recur at EDA
time too.

**`Forecastability & Intrinsic Predictability.md`** (139 lines) is
explicitly framed as upstream of the 13-step workflow — verbatim: *"This
sits upstream of the 13-step workflow in the hub guide. Think of it as
Step 0."* This is the one genuinely time-series-specific EDA idea not
mirrored anywhere else in the vault: before choosing a model, measure
whether the series is forecastable at all. Four measures given with
practical thresholds: **Permutation Entropy** (0=predictable, 1=random,
model-free), **Shannon Entropy Rate**, **Spectral Predictability**
(*"scores below 0.2 are indicative of low forecastability,"* cites Wang
et al. 2025), **Lyapunov Exponents** (*"largest... above 1.0 is indicative
of low forecastability,"* needs 100+ observations), **Sample/Approximate
Entropy** (correlates with out-of-sample MASE on M3). Practical framing:
*"Avoids wasted effort: If a series has near-zero intrinsic
predictability, throwing XGBoost, LSTMs, and transformers at it won't
help."*

**`Correlation, Autocorrelation and Cross-Correlation.md`** (167 lines)
gives ACF (`statsmodels.tsa.stattools.acf`), the correlation-vs-
autocorrelation distinction table ("are these two different things
related?" vs "does this one thing's past predict its future?"), and
cross-correlation for lead-lag detection with an explicit lag-sign
convention (k>0 → x leads y).

**`Decomposition Methods for Time Series.md`** (101 lines) covers Classical
(moving-average based, outlier-sensitive, constant seasonality assumed)
vs **STL** (`statsmodels.tsa.seasonal.STL`, robust to outliers when
`robust=True`, handles slowly-changing seasonality, no stationarity
requirement) vs X-11/X-12-ARIMA/SEATS/MSTL/TBATS for
multiple-or-non-integer seasonality. Decision table: strong evolving
seasonality → STL/MSTL; noisy periodic → STL(robust); want structural
understanding → Classical or STL; want forecast + calendar effects →
Prophet/TBATS. Explicit caveat: *"decomposition is a complementary tool,
not a requirement... not always beneficial for high-frequency or
irregular series."*

**`Dealing with Outliers in Time Series.md`** (42 lines, tight and fully
prescriptive). Same normality-gates-method pattern as the general Data
Cleaning note but time-series-specific in its caveat: **Z-score (3-sigma)
requires normality; IQR is distribution-free** and preferred for
skewed/heavy-tailed series. Three-step process: check normality
(histogram/QQ/Shapiro-Wilk) → pick method accordingly → **verify with
domain knowledge** ("Does the spike make business sense? Was there an
event that caused it?"). Distinctive time-series rule not present in the
generic cleaning note: *"you may want to model the outlier with a dummy
variable rather than remove it"* — because in forecasting, spikes are
often the signal (regime shifts, shocks), not noise.

**`Forecasting with ML — Lag Features, Hybrids & Tree Models.md`** (101
lines) gives the **lag-plot** technique (`lagplot()` helper, scatter of
series against its own lag, annotated with correlation) and the
**PACF-for-lag-selection** rule: ACF at lag 2 may be entirely decayed
information from lag 1; PACF isolates the "new" correlation each lag
contributes, so `plot_pacf` — not `plot_acf` — is the tool for choosing
which lags to feature-engineer. Explicit non-linearity caveat: *"ACF and
PACF are measures of linear dependence... use lag plots (or mutual
information) to check for non-linear structure before finalizing lag
features."*

**`Residual Diagnostics — How to Check for White Noise.md`** (105 lines)
is post-model, not pre-model EDA, but shares plotting/testing machinery
(ACF/PACF plots, Ljung-Box, Durbin-Watson) that a time-series EDA
playbook would also reach for on the raw series before modeling.
Recorded for completeness, tagged as borderline.

**Tags:** time-series (all of the above).

Candidate for playbook: **yes** for stationarity-check framing,
forecastability pre-screening, decomposition decision table, ACF/PACF
lag-plot technique, and the normality-gated-outlier-method-plus-
domain-check pattern — these together are close to a complete
time-series EDA playbook already. **Partial** for residual diagnostics
(genuinely post-model, include only as a forward pointer).

### Data Engineering — skim for ingestion-time profiling

Checked `Data Engineering/Data Pipelines & Formats/` (`Apache
Spark-pyspark.md` not opened — out of EDA scope by title;
`Data Engineering-End-to-end Pipelines.md` already covered by the sibling
pipeline-trawl atlas, §13) and its two smallest files directly:

- `Data Extraction.md` (193 lines) — a SQLAlchemy connection how-to
  (engine/connection/cursor lifecycle, Azure SQL credentials, `driver`
  parameter). One EDA-adjacent rule of thumb: *"if your database table is
  large, it's almost always better to filter in SQL first using
  `pd.read_sql_query` rather than loading the entire table... Workflow
  rule of thumb: if you know your filtering conditions → do them in SQL
  before loading."* No profiling, schema-inference, or data-quality-at-
  ingestion content.
- `File Types.md` (2 lines) — two bare URLs (Avro-vs-Parquet, file-format
  guide), no body content.

**Finding: no ingestion-time profiling notes exist in the vault.** Nothing
under Data Engineering discusses schema inference, column-type detection,
or quality gates at load time — that content, if it exists, lives only in
the Exploratory & Preparation cluster already covered above.

Candidate for playbook: **no** — nothing found to lift; recorded as a gap
below.

---

## Stated coverage by topic

| Topic | Notes covering it | Depth |
|---|---|---|
| tabular | Exploratory Data Analysis, Data Cleaning, Data Splitting & Scaling, Feature Encoding, Discussion-Boolean Flags, Imbalanced Data (imbalance table) | thorough |
| count | Exploratory Data Analysis (countplot/bar-chart path), Imbalanced Data (imbalance-degree table), Chi-Square Tests (categorical comparison) | partial |
| time-series | Time Series Forecasting hub, Forecastability, Correlation/ACF/PACF, Decomposition, Outliers-in-TS, Forecasting-with-ML lag features | thorough |
| geospatial | none | absent |
| text/NLP | EDA for NLP | thorough |
| images | EDA for Images | thorough (not on the original candidate list — see gaps) |
| generic decision-support (which stat test) | Statistical Inference hub, Parametric/Non-Parametric/Chi-Square/ANOVA guides | thorough |

## Candidate for playbook — per distinct technique/checklist

| Technique / checklist | Source note | Candidate | Why |
|---|---|---|---|
| 5-stage generic EDA order (preliminary → univariate → bivariate → outlier → correlation) | Exploratory Data Analysis | yes | closest thing to a generic spine; directly extensible |
| Pearson/Spearman assumptions + limitations table | Exploratory Data Analysis | yes | decision-support for correlation-analysis step, cross-topic |
| Image metadata-table construction (path/label/w/h/area/aspect/mode, corrupt-file handling) | EDA for Images | yes | complete, directly transplantable |
| Class-imbalance-ratio check (max/min) + 3-part response | EDA for Images | yes | generalizes beyond images to any classification topic |
| Resolution/aspect-ratio diagnostics driving transform choice | EDA for Images | yes | images-specific but complete |
| Forced-RGB / color-mode audit | EDA for Images | yes | images-specific, concrete rule |
| Blur/saturation/contrast (Laplacian variance, HSV) + percentile filters | EDA for Images | yes | images-specific, complete utility set |
| Text preprocessing function table (9 functions + rationale) | EDA for NLP | yes | complete, directly transplantable |
| Language-detection-as-filter step | EDA for NLP | yes | concrete, prevents corpus contamination |
| TTR / vocabulary-size / length metrics | EDA for NLP | yes | core lexical-diversity diagnostics |
| Label-vs-sentiment mismatch check | EDA for NLP | yes | concrete mislabeling-detection technique |
| Punctuation/capitalization as sentiment-magnitude features | EDA for NLP | partial | narrow to sentiment tasks specifically |
| 8-step data-cleaning workflow | Data Cleaning | yes | generic cleaning checklist, cross-topic |
| Post-hoc-feature / leakage warning | Data Cleaning | yes | short, quotable, cross-topic |
| Split-then-scale leakage rule | Data Splitting & Scaling | partial | pipeline-adjacent, but the rationale belongs in generic playbook |
| Stratified-split rationale | Data Splitting & Scaling | partial | EDA (class balance) gates this pipeline decision |
| One-hot vs ordinal drawback list | Feature Encoding | partial | pipeline mechanics; only the cardinality-check trigger is EDA |
| Mature-estate flag case study (multicollinearity in regression vs trees) | Discussion-Boolean Flags | partial | single worked example, illustrative not general |
| Imbalance-degree table (mild/moderate/extreme) | Imbalanced Data | yes | direct fit for tabular/count "check target distribution" step |
| Precision-Recall-over-ROC-under-imbalance rule | Imbalanced Data | partial | diagnostic-plot choice, borderline modeling |
| Resampling / class-weighting / label-smoothing / focal loss | Imbalanced Data | no | modeling response, not EDA |
| Which-significance-test decision tree | Statistical Inference hub | yes | short, precise, cross-topic decision support |
| Shapiro-Wilk/Levene's normality-and-variance gating | Parametric/Non-Parametric/ANOVA | yes | concrete pre-test checks an EDA step would run |
| Stationarity check (ADF/KPSS) as EDA Step 2 | Time Series Forecasting hub | yes | canonical time-series EDA step |
| Forecastability pre-screening (entropy/spectral/Lyapunov) | Forecastability & Intrinsic Predictability | yes | distinctive "Step 0" idea, unique to time-series in this vault |
| ACF/PACF + lag-plot for lag-feature selection | Correlation..., Forecasting with ML | yes | canonical time-series EDA technique |
| Decomposition method-selection table (Classical/STL/X-11/TBATS) | Decomposition Methods | yes | concrete decision table |
| Normality-gated outlier method + domain-check + "model the spike, don't remove it" | Dealing with Outliers in Time Series | yes | time-series-specific refinement of the generic outlier rule |
| Residual white-noise diagnostics (Ljung-Box, Durbin-Watson) | Residual Diagnostics | partial | post-model, only tangentially EDA |
| SQL-filter-before-load rule | Data Extraction | partial | ingestion-adjacent, not proper EDA, worth one line in a data-loading preamble |

## Gaps

**Candidate-list topics the vault does not cover:**

- **geospatial** — zero notes anywhere in the read set (primary or
  secondary) address spatial data: no CRS handling, no choropleth/point-
  map EDA, no spatial-autocorrelation (Moran's I) content. A geospatial
  playbook has no vault seed material at all.
- **count** — no note treats "count data" as its own EDA problem (e.g.
  overdispersion checks, Poisson/negative-binomial diagnostics, zero-
  inflation). What exists is scattered: the countplot path in the generic
  EDA note, the imbalance-degree table, and the Chi-Square guide for
  categorical comparisons. A count playbook would need to be assembled
  from generic-tabular pieces rather than lifted from a dedicated note.
- **tabular** — well covered overall, but no note explicitly treats
  cardinality assessment (how many unique values before one-hot becomes
  impractical) as an EDA step in its own right; it is implied by Feature
  Encoding's drawback list but never made into a checklist item or
  threshold.

**Topics the vault covers that were not on the candidate list:**

- **images** — the single most complete per-topic guide in the primary
  set (`EDA for Images.md`), not mentioned in the original candidate
  topic list (tabular, count, time-series, geospatial, text). Worth
  flagging explicitly: if the playbook set is meant to match the
  candidate list exactly, this is surplus content; if the list was
  illustrative rather than exhaustive, images should likely be added as a
  sixth playbook given how complete the source material already is.
- **statistical hypothesis testing as a cross-cutting decision layer** —
  not itself a "topic" in the tabular/count/time-series/geospatial/text
  sense, but the Statistical Inference cluster is thorough enough
  (decision tree, normality/variance gating, parametric-equivalent
  mapping) that it reads as a candidate for a shared "which test do I
  run" appendix referenced by multiple per-topic playbooks rather than a
  topic of its own.
- **time-series forecastability pre-screening** — the vault treats this
  as its own step ("Step 0," upstream of stationarity checks), which is a
  more developed idea than a plain stationarity-check EDA step; worth
  preserving as a distinct playbook section rather than folding it into a
  generic "check your data" step.

## Cross-vault duplication and quality notes

- `Feature Encoding.md` and `Pipelines.md` contain the **identical**
  `ColumnTransformer` code block, verbatim down to variable names. Neither
  cites the other. Mining both added no new content beyond note 7; note 11
  is otherwise empty.
- `Data Cleaning & Preprocessing.md` is self-marked superseded and "safe
  to delete" by the maintainer; it was read per the trawl-plan requirement
  but contributes nothing beyond a link list already present in note 4.
- `Feature Engineering.md` is a stub with a stray trailing character (`S`)
  suggesting an interrupted edit; `Feature Importance.md`, one of its
  three linked sub-topics, was not on the required-read list and was not
  independently verified to exist.
- The generic EDA note (`Exploratory Data Analysis.md`) and the
  cleaning/splitting notes are all built around a single running example
  (Singapore HDB resale-flat pricing). No note in the primary set uses a
  count-data, geospatial, or time-series-specific worked dataset — the
  vault's worked examples skew tabular even where the prose is general.
