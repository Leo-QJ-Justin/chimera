# EDA Trawl — all-assignments (AIAP coursework), Pass 2

> Research artifact for chimera. Mined 2026-08-03 (Pass 2 of the approved
> EDA-playbooks research trawl; Pass 1 covers the maintainer's Obsidian
> vault, `docs/research/2026-08-03-eda-trawl-atlas.md`). Source:
> `~/all-assignments`, branches `origin/qjjustin_leo` (the maintainer's,
> read in full), `origin/Parthiban_Meyyar` (a peer branch newly added to
> the corpus, read in full and diffed against the maintainer's), and
> `origin/li_yang_chew` / `origin/dengfeng_zhou` (diff-only, read further
> only where the diff showed substantive EDA divergence). `origin/main`
> (the unfilled AISG scaffold) is used throughout to separate
> course-authored canon from trainee fill-in. All findings are static
> reads via `git show origin/<branch>:<path>` and `git diff <ref> <ref>
> -- <path>` against a detached-HEAD checkout that was never moved;
> nothing was executed. Method follows
> `docs/research/2026-07-30-pipeline-trawl-all-assignments.md`:
> evidence-first, per-branch diff, honest grading including
> anti-patterns.

## 1. Scope and the scaffold/fill-in boundary

Seven EDA-bearing notebooks were in scope. Two of them —
`assignment4/A4P2_eda.ipynb` and `assignment4/A4P3_data_cleaning.ipynb`,
the "EDA at scale" Spark notebooks — turned out to be **pure AISG
scaffold across all four branches examined**. Diffing each against
`origin/main` shows the only difference on any branch is the single
`yourname` placeholder substitution (`justinleo`, `parthiban`,
`zhoudengfeng`); `origin/li_yang_chew`'s copy is byte-identical to the
unfilled scaffold, meaning that branch never ran or filled in the
notebook at all. `origin/dengfeng_zhou`'s copy adds one empty executed
cell and a markdown/code cell-order swap — a re-execution artifact, not
new content. Section 2 below therefore treats A4P2/A4P3 as
course-authored canon and reports the walkthrough itself rather than any
trainee's fill-in; there is no meaningful branch-divergence signal to
report for these two files and they do not appear in Section 3.

The remaining five notebooks (`A1P1_eda_extended`, `A6P1_eda_data_
cleaning`, `A7P1_nlp_introduction`, `A5P1_introduction`,
`A5P2_classification`) are genuine fill-ins with heavy scaffold/trainee
mixing: markdown headers, section numbering, and the guiding questions
are canon (verified against `origin/main`); code cells, written
observations, and any added markdown are the trainee's. Findings below
are drawn from the trainee-authored portions only, cited by branch.

## 2. Per-notebook findings — the maintainer's branch (full read)

### 2.1 `assignment1/A1P1_eda_extended.ipynb` — tabular EDA baseline

SQL extraction (`sqlalchemy` + `pyodbc` driver string) to a local csv,
then a linear EDA sequence on a census-income subset (~31k rows, 43
features, target `income_group`):

1. `head()` / `info()` / `isna().sum()` / `describe().T` /
   `duplicated().sum()` — the standard first pass. Only one column
   (`hispanic_origin`, 114 rows) carries nulls; zero duplicate rows.
   Tag: tabular, generic.
2. Dtype recast: four numeric-looking columns
   (`detailed_industry_recode`, `detailed_occupation_recode`,
   `own_business_or_self_employed`, `veterans_benefits`) are cast to
   `object` because they are coded categoricals, not measurements — a
   reminder that `describe()` output must be sanity-checked against
   domain knowledge, not trusted from dtype alone. Tag: tabular.
3. Per-column unique-value dump for every object column
   (`census_dataset[col].unique()`), which surfaces sentinel-like
   placeholder categories ("Not in universe", "?", "Do not know") that
   are semantically missing but not `NaN`. Tag: tabular. **Candidate for
   playbook: yes** — placeholder-category detection via unique-value
   scan is cheap and catches a failure mode `isna()` alone misses.
4. Univariate histograms for every numeric column in one subplot grid
   (`sns.histplot(..., kde=True, bins=30)`), revealing extreme
   right-skew in `wage_per_hour`, `capital_gains`, `capital_losses`,
   `dividends_from_stocks` with maxima pinned at 9999/99999 — read as
   placeholder-value suspects, not genuine outliers. Tag: tabular.
5. Z-score outlier filter (`|z| < 3`) on the four skewed columns,
   re-describing and re-plotting the filtered frame to confirm the
   9999/99999 ceiling disappears (~2.7k rows dropped). Tag: tabular.
   **Candidate for playbook: yes** — the before/after
   describe-then-replot pattern for validating an outlier-filter
   decision is directly reusable.
6. Bar chart per categorical column (`value_counts(normalize=True)`),
   used to spot high-cardinality, near-constant columns worth collapsing
   before one-hot encoding. Tag: tabular.
7. Redundancy check via `drop_duplicates()` on column *pairs*
   (`detailed_industry_recode` vs `major_industry_code`) to confirm two
   columns encode the same information at different granularity. Tag:
   tabular. **Candidate for playbook: yes** — a direct, cheap test for
   "are these two columns really independent features," more concrete
   than eyeballing a correlation heatmap.
8. Boxplot of a numeric feature split by a categorical
   (`wage_per_hour` by `full_or_part_time_employment_stat`), which
   surfaces a data-quality problem: full-time workers show `wage_per_hour
   == 0`, contradicting the feature's stated meaning and motivating
   dropping it entirely rather than imputing. Tag: tabular. **Candidate
   for playbook: yes** — boxplot-by-category as a *feature-validity*
   check, not just a distribution check, is the more valuable framing.
9. `pd.crosstab(target, feature, normalize="columns")` repeated for
   three categorical features against the target — the bivariate
   category-vs-target view. Tag: tabular.
10. Pearson correlation heatmap on a manually curated numeric subset
    (`sns.heatmap(..., cmap='coolwarm', vmin=0, center=0.5, vmax=1)`),
    with one strong pairwise correlation (0.72) called out and
    interpreted. Tag: tabular.
11. Narrative synthesis: a written paragraph grouping every feature into
    "drop / re-aggregate / redundant-pick-one" buckets, closing the loop
    from EDA finding to concrete feature-engineering action. Tag:
    tabular, generic. **Candidate for playbook: yes** — the
    finding-to-action grouping is a good closing template for any
    tabular EDA writeup.
12. External-tool survey: Google Facets, `ydata_profiling.ProfileReport`
    (`profile.to_file(...)`), and `dtale.show()`, each used once with a
    short written comparison of strengths (Facets: train/test-split
    balance view + regex search; ydata: automated correlation/imbalance
    flagging; dtale: spreadsheet-like interactive filtering). Tag:
    tabular, generic. **Candidate for playbook: partial** — worth a
    one-line pointer to auto-profiling tools in the generic playbook,
    not worth reproducing the tool survey itself.

### 2.2 `assignment4/A4P2_eda.ipynb` + `A4P3_data_cleaning.ipynb` — EDA at scale (canon, all branches)

Course-authored PySpark walkthrough against an HDB resale-price Delta
table. Since this is unmodified canon (Section 1), it is reported as a
technique inventory rather than a trainee's fill-in.

A4P2 (EDA): `df.printSchema()`; `df.describe().show()`; per-column mean/
stddev via `.agg({col: "mean"/"stddev"})`; `groupBy(...).count()`;
filter-above-mean row inspection; `show(1, vertical=True)` for a
single-row deep look; column rename and dtype cast
(`withColumnRenamed`, `withColumns({...: col.cast(T.IntegerType())})`);
`describe()` restricted to the now-integer columns; `countDistinct` per
string column via a list comprehension of aggregate expressions; column
slicing (`select`); multi-categorical + regex row filtering
(`.isin([...])` combined with `.rlike("^SER.*")`); ad hoc `spark.sql()`
querying; the `%%sql` and `%%spark -o` / `%%local` magics for
in-notebook visualization and Spark-to-pandas handoff; a Pearson
correlation matrix over all integer columns via
`VectorAssembler` + `pyspark.ml.stat.Correlation.corr`. Tag: tabular,
generic.

A4P3 (data cleaning): schema/describe/show recap; dtype casts; duplicate
count broken into total/distinct/duplicate followed by
`dropDuplicates()`; feature engineering via `regexp_extract` (parsing
"NN years NN months" free text into two integer columns) and
`substring` (year/month from a compound date string); a custom
`@pandas_udf` for row-wise range-string averaging
(`"10 TO 12"` → `11`); unneeded-column drop; missing-value counting that
combines four conditions in one pass (`contains('None')`,
`contains('NULL')`, `== ''`, `isNull()`, `isnan()`); **three missing-value
treatments compared explicitly side by side** — constant-fill, row-drop,
and `pyspark.ml.feature.Imputer` mean-fill — without picking a winner in
the notebook (left as a live comparison); outlier filtering via
mean ± 3·stddev with an explicit before/after stddev/mean printout; a
final write to a Delta "silver" table. Tag: tabular, generic.
**Candidate for playbook: yes** — the three-way missing-value-treatment
comparison and the before/after-statistics outlier-filter pattern are
both generic and directly reusable outside Spark; the four-condition
missing-value scan (catching string "None"/"NULL"/empty-string in
addition to true nulls) is a good defensive pattern for any
loosely-typed source.

### 2.3 `assignment6/A6P1_eda_data_cleaning.ipynb` — time-series EDA & cleaning

The most technique-dense notebook in the corpus, against hourly Beijing
PM2.5 + meteorological data. All tag: time-series unless noted.

1. Conceptual grounding first: stationarity, trend/seasonal/cycle,
   additive vs multiplicative decomposition, three approaches to
   encoding time as a feature (dummy variables, sin/cos cyclical
   encoding, radial basis functions) — each with a written pros/cons
   comparison tied back to the decomposition framework.
2. `statsmodels.tsa.seasonal.seasonal_decompose`, additive and
   multiplicative side by side on monthly-resampled data (with a `+1`
   shift to keep the multiplicative model defined at zero).
3. Data load → `head()` / `info()` / `isna().sum()` / `describe().T` /
   `duplicated().sum()` — same first pass as tabular EDA, on a
   timestamp-indexed frame.
4. **Missing-timestamp reconstruction**: build a full expected hourly
   `pd.date_range`, left-merge the raw data onto it, `groupby` the
   resulting NaN rows by year/month/day to list missing days, then use a
   boolean-diff + `cumsum()` trick to label contiguous valid stretches
   and find the single longest unbroken run (used later to scope the ACF
   analysis to a clean window).
   ```
   mask = cross_data['pm2.5'].notna().astype(int)
   cross_data['block'] = (mask.diff(1) != 0).cumsum()
   valid_blocks = cross_data[mask == 1].groupby('block').size()
   ```
   **Candidate for playbook: yes** — this is the one technique in the
   whole corpus that treats "is the time axis itself complete" as a
   distinct EDA question from "are there missing values," and the
   longest-contiguous-block trick is a clean, reusable way to answer it.
5. Univariate line plots at five temporal scales — full span (too dense
   to read, an explicit negative finding), monthly aggregate (reveals
   seasonality), a single year, a single week, a single day, and
   year-on-year aligned by day-of-year (`hue='year'`) — each scale
   yielding a different, stated insight. **Candidate for playbook:
   yes** — the multi-scale-on-purpose framing (not just "plot it") is
   worth codifying as a checklist.
6. Histograms per feature, with an explicit caveat that a frequency
   histogram alone cannot show temporal structure, followed by a
   monthly-hue KDE (`sns.kdeplot(..., hue='month', common_norm=False)`)
   to see distribution shift across the year.
7. Pairwise scatter (`sns.pairplot`) + correlation heatmap, with an
   explicit spurious-correlation caveat (i.i.d. violation) attached
   directly to the correlation step rather than left implicit.
8. Spurious-correlation demonstration: first-difference two correlated
   raw features (`difference(t) = obs(t) - obs(t-1)`), plot raw vs.
   differenced scatter side by side, then an **interactive
   plotly + ipywidgets lag slider** (lag 1–10) recomputing the
   differenced correlation live. **Candidate for playbook: partial** —
   the differencing-to-detrend technique is core; the interactive
   widget is a nice-to-have, not essential for a static playbook.
9. Rolling-mean smoothing at three window sizes (2/5/12) overlaid on one
   plot to show the smoothing/responsiveness trade-off; then
   non-overlapping downsampling via `resample('6H').mean()`, with an
   explicit note that downsampling is not the same operation as
   smoothing (frequency changes vs. values change).
10. SMA/EMA/TEMA/SMMA computed and compared on one plot, judged from the
    plot (TEMA most responsive to the underlying signal). Tag:
    time-series. **Candidate for playbook: partial** — SMA/EMA are
    standard; TEMA/SMMA are a nice-to-have for a "moving-average family"
    reference table but not core.
11. ACF plots (`statsmodels.graphics.tsaplots.plot_acf`) paired
    side-by-side with the univariate plot per feature, restricted to the
    longest clean block from step 4, explicitly used to justify a 24-hour
    window for later imputation ("persistence through ACF" reasoning).
    **Candidate for playbook: yes** — ACF-justifies-imputation-window is
    the strongest causal chain in the corpus (EDA finding → concrete
    cleaning parameter), and pairing ACF with the matching univariate
    plot is a good visual habit.
12. Periodograms (`scipy.signal.periodogram`) per feature with vertical
    reference lines at daily/weekly/monthly frequencies, read for
    feature-engineering guidance (which cycles are worth encoding).
    **Candidate for playbook: yes** — periodograms are otherwise absent
    from the corpus and are a genuinely useful frequency-domain
    complement to ACF for spotting periodicity.
13. Missing-data treatment: forward-fill, backward-fill, and a manual
    centered rolling-mean(24) imputation, with the rolling-mean choice
    explicitly reasoned from the ACF-persistence finding in step 11 —
    then a **re-check** for remaining timestamp breaks after imputation
    (closing the loop opened in step 4).
14. Downsample to 10-day means, then upsample back to hourly via
    `resample('H').asfreq()` + `interpolate(method='time')`, with a
    written discussion of the information loss this round-trip causes.
    Tag: time-series. **Candidate for playbook: yes** — demonstrating
    upsample-after-downsample information loss concretely (rather than
    asserting it) is a good teaching pattern.

### 2.4 `assignment7/A7P1_nlp_introduction.ipynb` — text/NLP exploration

IMDB movie-review sentiment data. Only the exploration-relevant portion
is reported (data extraction through vectorization); model-training
mechanics are out of scope per the trawl brief. All tag: text/NLP.

1. Standard first pass adapted for text: `isna().sum()`,
   `duplicated().sum()` + drop, `text.str.len().describe()` +
   histogram (reveals a long right tail — one extreme outlier reviewed
   directly via `textwrap.fill`).
2. HTML-artifact detection via a `BeautifulSoup(...).find()` boolean
   flag column, `value_counts()`, then direct inspection of flagged
   rows. Tag: text/NLP. **Candidate for playbook: yes** — a boolean
   "does this row contain artifact X" column, generalized, is a clean
   pattern for auditing any suspected contamination in free text.
3. Label-distribution check (near-balanced, so no resampling/weighting
   needed) plus a **text-length-binned label-distribution stacked bar**
   — checking whether review length itself leaks information about the
   label, a check specific to text that a plain `value_counts()` would
   miss. **Candidate for playbook: yes** — length-vs-label is a cheap,
   text-specific leakage check worth naming explicitly.
4. A 9-step regex/BeautifulSoup cleaning pipeline (HTML tags → URLs →
   lowercase → accent-strip via `unicodedata.normalize('NFKD', ...)` →
   contraction expansion via the `contractions` package → mentions/
   hashtags → digits → special characters → punctuation), with **each
   step tracked by an explicit before/after boolean `affected_X`
   column**, summed into a per-record "how many steps touched this
   review" histogram — quantifying that only one record in the corpus
   needed zero cleaning.
   ```
   cleaned_data['step1_no_html'] = cleaned_data['original_text'].apply(remove_html_tags)
   cleaned_data['affected_html'] = cleaned_data['original_text'] != cleaned_data['step1_no_html']
   ```
   **Candidate for playbook: yes** — the per-step affected-row tracking,
   generalized into a reusable helper, is the single most valuable text
   technique in the corpus: it turns "I cleaned the text" into an
   auditable, quantified claim.
5. A 3-way stemmer bake-off (Porter via `nltk`, Snowball/English via
   `nltk`, Krovetz via `krovetzstemmer`), each timed on the same sample
   document, compared with a **positional word-diff helper** that prints
   only the tokens where two stemmed outputs disagree — much faster to
   read than diffing full stemmed strings. Krovetz judged best on
   subjective inspection (most complete words) and fastest despite its
   reputation for being slow on long text.
   **Candidate for playbook: yes** — the positional-diff comparator
   generalizes to any two competing text-normalization outputs
   (stemmer vs. stemmer, stemmer vs. lemmatizer, cleaning-version A vs.
   B), not just this one comparison.
6. WordNet lemmatization run through the same positional-diff comparator
   against the winning stemmer, judged slower and prone to preserving
   tense/inflection that the stemmer collapses.
7. Bag-of-Words via `CountVectorizer`, with a single-document
   word/count table (sorted descending) as the concrete "what does BoW
   actually produce" check, plus a written observation about
   dimensionality/sparsity trade-offs.
8. TF-IDF via `TfidfTransformer` layered on the same BoW counts, using
   the identical single-document inspection, then **merged against the
   BoW table on the shared word column** to show side by side that
   high-frequency words are not the same as high-TF-IDF words. Tag:
   text/NLP. **Candidate for playbook: yes** — the merged BoW-vs-TF-IDF
   single-document comparison is a concrete, minimal way to teach why
   TF-IDF re-weights frequency, better than describing the formula
   alone.
9. A custom `Tokenizer` class bundling the full clean → stem pipeline
   behind a single `tokenize()` method, built specifically so it can be
   handed to `sklearn`'s vectorizers as `tokenizer=...`. Tag: text/NLP,
   generic. **Candidate for playbook: yes** — packaging the
   cleaning+normalization pipeline as one class with a single entry
   point is good practice regardless of the specific steps chosen.

### 2.5 `assignment5/A5P1_introduction.ipynb` + `A5P2_classification.ipynb` — image data

A5P1 is almost entirely image-transformation *mechanics* (`PIL` load,
`img.format`/`img.size`/`img.mode`, NumPy tensor shape/dtype inspection,
brightness/contrast/saturation sweeps, affine transform sweeps,
hand-computed and library convolution kernels) rather than exploration
of a real dataset — it operates on one placeholder image throughout. The
only exploratory content worth noting: inspecting a single image's
`(format, size, mode)` and reasoning explicitly about why pixel data is
`uint8` (8-bit unsigned range 0–255 matching RGB). Tag: images (thin).
**Candidate for playbook: no** — not enough dataset-level content to
generalize; the transform mechanics belong in an augmentation reference,
not an EDA playbook.

A5P2's EDA section (tensorfood food-image classification, 12 classes,
1236 images) is the corpus's most deliberate "EDA before augmentation"
methodology — explicitly framed as informing feature-engineering choices
rather than as a standalone checklist. Tag: images throughout.

1. Per-class image count and proportion — a direct class-imbalance
   check (highest class 13.92%, lowest 5.26%, ~2.5x span).
2. Corpus-wide PIL mode/format scan (every image opened, `mode` and
   `format` tallied into dicts) — catches inconsistent file formats and
   colour modes across the dataset before they become a preprocessing
   surprise.
3. Per-class mean R/G/B channel value (accumulated channel sums divided
   by pixel count, per class), bar-plotted — a direct test of whether
   classes are colour-separable before betting an augmentation strategy
   on colour. **Candidate for playbook: yes** — per-class mean-channel
   value is a cheap, general "is colour a usable signal" check for any
   image classification EDA.
4. A **seeded** random sample of 3 images per class
   (`np.random.default_rng(seed=42)`), with each sampled image's
   `(format, size, mode)` printed individually — catching inconsistent
   resolution at the sample level, distinct from the corpus-wide scan in
   step 2. Tag: images, generic. **Candidate for playbook: yes** — using
   a scoped `Generator` rather than the global `random` module for
   reproducible sampling is worth stating as the default pattern.
5. A labeled sample grid (one row per class, three columns) with a
   **written, per-class observation answering a fixed EDA question
   list** — colourised? object position/centering? relative object
   size? orientation? distinctive class features? — turning a visual
   skim into a structured, comparable record per class.
   **Candidate for playbook: yes** — the fixed-question-list-per-sample-
   row pattern is directly reusable as an image-EDA checklist template.
6. Hypothesis-driven augmentation selection: a stated
   observation → technique → expected-metric-change template
   ("I observe that _, hence I want to try _ because _. I expect _ to
   increase/decrease"), applied to CLAHE contrast enhancement with a
   before/after comparison grid across the sampled images. Tag: images,
   generic. **Candidate for playbook: yes** — the observation-hypothesis-
   expected-outcome template closes the loop from EDA finding to a
   falsifiable augmentation choice, which is a stronger discipline than
   "try some augmentations."

## 3. Branch divergence

### 3.1 Peer branch (`origin/Parthiban_Meyyar`) vs. the maintainer's branch

This branch is a genuinely independent fill-in throughout — own written
interpretations, own numeric findings, own dataset-specific reasoning —
not a copy of the maintainer's or scaffold's prose. It diverges heavily
on every notebook, in both directions.

**A1P1 (tabular).** Loads via `pyodbc` directly rather than
`sqlalchemy`; drops the `id` column early and systematically loops every
column printing unique-value counts and proportions (low-cardinality:
all values; high-cardinality: top 10), rather than the maintainer's
single unique-value dump. Converts `"?"` placeholders to an explicit
`"Unknown"` category (the maintainer's branch flags but does not act on
these). After each analysis stage inserts a numbered, structured
**"Observations" markdown block** synthesizing that stage's findings
before moving on — a more disciplined write-up cadence than the
maintainer's end-of-notebook synthesis. Tag: tabular. **Worth
adopting** — the per-stage observation block is a better documentation
habit than a single closing paragraph.

Adds techniques absent from the maintainer's branch entirely:
- Spearman correlation heatmap alongside Pearson, explicitly for the
  non-linear/monotonic case.
- Boxplot of every numeric feature against the target
  (`income_group`), not just one feature as the maintainer does.
- Stacked proportion bar charts (`pd.crosstab(..., normalize="index")`)
  for every categorical feature against the target, split into
  low-cardinality and high-cardinality panels.
- **Cramér's V heatmap** for categorical-categorical association
  (chi-square-based), entirely absent from the maintainer's branch,
  which has no categorical-vs-categorical association measure at all.
  ```
  def cramers_v(x, y):
      confusion_matrix = pd.crosstab(x, y)
      chi2 = ss.chi2_contingency(confusion_matrix)[0]
      ...
  ```
- Ordinal encoding of `education` against an explicit rank list
  (`edu_order`), then a boxplot and a mean-trend line plot of
  `weeks_worked_in_year` by encoded education level — treating an
  ordinal feature as ordinal rather than nominal, which the maintainer's
  branch never does anywhere in the corpus.
- A third external EDA tool, **Sweetviz**, run with the binarized target
  as `target_feat`, replacing the maintainer's `dtale` — Sweetviz's
  target-conditioned analysis is a better fit for a supervised EDA task
  than dtale's general-purpose spreadsheet view.

Tag for all of the above: tabular. **Candidate for playbook: yes** for
Cramér's V (fills a real gap — the maintainer's branch has no
categorical-association measure), the per-target boxplot/proportion-bar
sweep across *all* features rather than a hand-picked few, and
target-conditioned profiling (Sweetviz-style) as the preferred
auto-profiling tool over a general-purpose data viewer.

**A6P1 (time-series).** Also a genuinely independent fill-in — inserts a
large self-written primer (not present in either the scaffold or the
maintainer's branch) covering lookahead bias, ADF stationarity testing,
ACF/PACF, `tsfresh` feature generation, and a model taxonomy
(AR/ARIMA/VAR, Kalman filter, HMM, BSTS, XGBoost, CNN/RNN/LSTNet).
Concrete technique divergences:
- Adds **STL decomposition** (`statsmodels.tsa.seasonal.STL(...,
  seasonal=365, robust=True)`) alongside the classical
  `seasonal_decompose` both branches share — an outlier-robust,
  LOESS-based decomposition the maintainer's branch lacks. Tag:
  time-series. **Worth adopting.**
- Adds a richer rolling-statistics dashboard (rolling std, min/max
  range, median+IQR, rolling skewness via `scipy.stats.skew`) as a
  6-panel view, in place of (not in addition to) the maintainer's
  SMA/EMA/TEMA/SMMA family. Tag: time-series. **Worth adopting as a
  complement** — genuinely useful additions, but the exponential-family
  smoothers are lost, so it is a substitution rather than a strict
  upgrade.
- Applies a global `ffill` immediately after loading and reuses that
  frame for every downstream statistic (histograms, correlation,
  pairplot, rolling stats, ACF, periodogram) *before* any
  persistence-based justification for the imputation method is made —
  the ACF-reasoning step exists but is applied later to separate copies,
  not to the frame already used upstream. Tag: time-series. **Avoid** —
  this is circular: a forward-filled run is by construction maximally
  autocorrelated, so ACF/periodogram figures computed on the
  pre-imputed frame partly measure the imputation, not the signal. The
  maintainer's branch orders this correctly (reason from ACF on real
  gaps, then impute).
- Skips the maintainer's full-`date_range` reconstruction of the
  expected timestamp grid; only detects `NaN` values inside an
  already-built index. Tag: time-series. **Avoid** — silently misses
  wholly missing rows (not just missing values), which the
  maintainer's approach catches explicitly.
- Encodes wind direction as a non-cyclic ordinal integer map
  (`{'NW': 0, ..., 'cv': -1}`, no wraparound handling) and then feeds it
  into Pearson correlation, `pairplot`, ACF, and periodogram analyses as
  if continuous. Tag: time-series. **Avoid** — inconsistent with the
  branch's own stated cyclical-encoding methodology (covered in its
  primer section) and produces close-to-meaningless linear-correlation
  and frequency-domain statistics on an arbitrary code.
- The interactive lag-slider spurious-correlation check is reduced to
  prose assertion ("yes, it changes at higher lags") with no
  supporting code for lag > 1. Tag: time-series. **Avoid** — an
  unverified claim where the maintainer's branch has a working,
  interactive demonstration.

**A7P1 (text/NLP).** Loads credentials via `python-dotenv`
(`load_dotenv()` + `os.getenv(...)`) instead of hardcoding them in the
notebook — not itself an EDA technique, but a real practice difference
worth carrying into any lifted extraction snippet. Divergent EDA/
cleaning content:
- A **corpus-wide regex artifact taxonomy** (HTML tags, HTML entities,
  backslash/dash runs, URLs, digit sequences), each scanned
  independently with `.str.contains` and reported as a percentage of
  the corpus, then **baked directly into the cleaning function's
  docstring** (`"HTML tags... (58.40% of reviews)"`) so the
  quantification travels with the code that acts on it. Tag: text/NLP.
  **Worth adopting** — ties the diagnostic straight to the
  justification, though it is corpus-level, not the maintainer's
  per-record `affected_X` tracking.
- A **vocabulary-size comparison** across cleaned / stemmed /
  lemmatized text stages (`len(set(' '.join(df[col]).split()))` per
  stage) — a concrete, cheap view of how much each normalization step
  compresses the vocabulary, absent from the maintainer's branch. Tag:
  text/NLP. **Worth adopting.**
- **Word clouds** at each processing stage, plus a positive-vs-negative
  sentiment split and a BoW-count-vs-TF-IDF-weight split. Tag:
  text/NLP. **Worth adopting** — the sentiment-split cloud in
  particular is a genuinely new, if purely qualitative, visual
  technique for eyeballing class-associated vocabulary.
- **Bigram frequency analysis** (`nltk.ngrams`, top-15 bar plot) —
  directly tests the notebook's own "Bag of Words loses word order"
  discussion point with real numbers rather than leaving it asserted.
  Tag: text/NLP. **Worth adopting.**
- Checks for duplicates (`duplicated().sum()`) but never calls
  `drop_duplicates()` anywhere in the notebook. Tag: text/NLP. **Avoid**
  — the EDA finding is never acted on, leaving a train/test leakage
  risk the maintainer's branch closes.
- Has no text-length distribution EDA at all (no `describe()`/histogram
  on review length, and no length-vs-label check). Tag: text/NLP.
  **Avoid** — a whole sub-step of the maintainer's canon sequence is
  skipped outright.
- A cleaning-function bug: `re.sub(r'[^a-zA-Z\s]', ' ', text)` strips
  apostrophes to spaces, turning `"don't"` into `"don t"`; a downstream
  short-token filter then drops the isolated `"t"`, silently collapsing
  negations (`"don't"`/`"isn't"` → `"don"`/`"isn"`) — a real
  sentiment-relevant defect, not a style choice. Tag: text/NLP.
  **Avoid.**
- Replaces the maintainer's 3-way empirically-timed stemmer bake-off
  with hand-written qualitative pros/cons tables and uses only the
  Porter stemmer in code. Tag: text/NLP. **Equivalent** — same
  tradeoffs covered narratively, but no empirical comparison backs the
  final choice.

**A5P2 (images).** A5P1 confirmed mechanics-only on both branches,
nothing to report. On A5P2's EDA section:
- Replaces the maintainer's per-class mean-RGB-channel analysis with a
  **corpus-wide resolution/aspect-ratio/channel/format scan**: every
  image's width, height, aspect ratio, file suffix, and channel count
  (via `np.array(img).shape`) collected into summary statistics
  (min/max/mean/median) and a 2×2 histogram grid. Tag: images. **Worth
  adopting** — a genuinely different, useful statistic (resolution
  spread 274–1300px width) that directly motivates a later
  `RandomResizedCrop` choice; the channel-count-via-array-shape check is
  cleaner than a mode-string comparison. Traded off, not added to, the
  color-separability check, which this branch drops entirely — **avoid**
  as an omission, since the later `ColorJitter` choice is then justified
  only impressionistically rather than from measured per-class color
  stats.
- Samples via the stdlib `random.seed(42)` / `random.sample` rather than
  a scoped `numpy.random.Generator`. Tag: images. **Avoid** — mutates
  global interpreter RNG state, less composable/reproducible than the
  maintainer's local `Generator`.
- Structures augmentation selection as **five explicit numbered
  hypotheses**, each pairing one observation to one named technique with
  concrete parameters (class imbalance → `WeightedRandomSampler` +
  `RandomErasing`; resolution variability → `RandomResizedCrop`;
  rotation → `RandomRotation(20)`; lighting → `ColorJitter`; occlusion →
  `RandomErasing`), instantiated as named pipelines and compared in one
  combined before/after grid. Tag: images. **Worth adopting** — a
  clearer, more scalable pattern than the maintainer's single
  one-technique-at-a-time narrative, even though the CLAHE/
  texture-vs-color reasoning itself does not appear on this branch.

### 3.2 Diff-only branches (`origin/li_yang_chew`, `origin/dengfeng_zhou`)

Read only where a diff against the maintainer's branch showed
substantive content divergence, not cosmetic noise (username strings,
re-execution artifacts, reordered-but-identical cells).

**A1P1 (tabular).**
`li_yang_chew` states an explicit 3-step feature-selection method —
check distribution, check predictive power via a stacked count plot
against the target, then justify the drop/keep decision — more
procedural than the maintainer's ad hoc grouping. **Worth adopting.**
It skips the maintainer's z-score outlier capping entirely (**avoid** —
drops a justified step) and carries leftover plot titles from an
unrelated HDB dataset ("Violin Plot of Enrollment...") — a copy-paste
tell (**avoid**).
`dengfeng_zhou` computes both Pearson and Spearman on a correlation
frame that includes the binarized target itself (**worth adopting** —
target-inclusive correlation the maintainer's branch doesn't do) and
adds a Cramér's V heatmap independently of the peer branch above
(**worth adopting**, corroborating that this is a real gap in the
maintainer's version). It also leaves `veterans_benefits` — a column
the maintainer's branch explicitly recasts to categorical — numeric in
that same correlation frame, producing a spurious 0.66 correlation with
age. **Avoid** — a real bug, and a second, independent illustration
(alongside §3.1's Cramér's V finding on the same feature-target frame)
that skipping an explicit dtype-recast step before correlation analysis
produces misleading numbers.

**A6P1 (time-series).**
`li_yang_chew` adds ACF-with-confidence-interval plots at raw, monthly,
and daily granularity (vs. the maintainer's single `plot_acf` call) and
ties the imputation-method choice explicitly to AR persistence
(φ 0.7–0.9 → forward/backward fill; low persistence → mean fill) — a
more formalized version of the maintainer's own ACF-justifies-
imputation reasoning. **Worth adopting**, though the actual imputation
code (a blanket `interpolate(method='linear')`) does not reflect this
framework — **avoid** for that specific gap between stated reasoning and
executed code.
`dengfeng_zhou` demonstrates `seasonal_decompose` only on a synthetic
sine wave, dropping the maintainer's real monthly-resampled
decomposition and its 2012 trend-anomaly finding entirely — **avoid**,
a real result lost. It does add a richer upsampling comparison
(ffill/bfill/linear/cubic/nearest-neighbor side by side with a written
pros/cons summary) in place of the maintainer's single
`interpolate(method='time')` — **worth adopting**.

**A7P1 (text/NLP).**
Both branches independently fix the same latent bug in the maintainer's
lemmatization call — `wnl.lemmatize(word)` has no part-of-speech
argument and silently defaults to noun, so it never reduces verbs — by
adding POS-tagged lemmatization. **Worth adopting**, and the fact that
two independent branches converged on the same fix is corroborating
evidence it is a real gap, not a style preference.
`li_yang_chew` additionally finds that punctuation frequency correlates
with sentiment label (question marks skew negative) via a
punctuation-frequency-by-label breakdown — a genuine new insight absent
from every other branch — and adds a VADER sentiment-score histogram by
label and per-label word clouds. **Worth adopting**, all three. It
narrows the maintainer's 3-way stemmer comparison to Snowball only —
**avoid**, less thorough than canon here.
`dengfeng_zhou` contributes only the POS-tagged lemmatization fix and is
otherwise narrower than both the maintainer's and `li_yang_chew`'s
branches (Porter-only stemming, no word clouds, no punctuation or VADER
analysis).

**A5P1/A5P2 (images).**
On A5P1, `li_yang_chew` shows one adjusted image per transform instead
of the maintainer's factor-sweep grid (0/1/2) — **avoid**, loses the
comparative view that makes a parameter's effect legible — and applies
a custom edge kernel with no written interpretation (**avoid**).
`dengfeng_zhou` applies both horizontal and vertical Sobel kernels
where the maintainer's branch applies only the left/horizontal one —
**worth adopting**, a cheap, more complete edge-detection demonstration.
On A5P2, `li_yang_chew` reasons explicitly from a min/max class-count
ratio (0.35) into a documented `WeightedRandomSampler`/class-weight/
stratified-split decision, where the maintainer's branch computes the
same numbers but only calls the imbalance "slight" with no downstream
decision attached — **worth adopting**, closes the finding-to-action
loop the maintainer's branch leaves open. It also runs a per-class
mean-RGB/pixel-intensity analysis surfacing real color bias (independent
corroboration that this is a valuable check, per §3.1's
`origin/Parthiban_Meyyar` finding) and a corrupted-image/channel-count
audit, neither present in the maintainer's branch — **worth adopting**,
both.
`dengfeng_zhou`'s A5P2 states the class distribution is "relatively
balanced with ~100 images per class," glossing over the same 64–171
(~2.65×) spread every other branch flags, and takes no corrective
downstream action (no stratified split, no class weighting anywhere in
the notebook). **Avoid** — an inaccurate read of the branch's own
numbers with no consequence drawn from it, which is a worse outcome
than not measuring the imbalance at all.

## 4. Practiced coverage by topic

| Topic | Notebooks providing evidence | Depth |
|---|---|---|
| tabular | A1P1 (all 4 branches read/diffed), A4P2/A4P3 (canon) | Deep. Richest single-notebook coverage plus four independent fill-ins; peer branches add categorical-association (Cramér's V) and target-conditioned analysis the maintainer's branch lacks entirely. |
| count | A4P2/A4P3 (`groupBy().count()`, `countDistinct`), A1P1 (`value_counts`) | Thin. Only ever appears embedded inside tabular EDA as a summary statistic — no notebook treats count/rate data as its own modeling concern (no dispersion check, no Poisson/rate reasoning). |
| time-series | A6P1 (all 4 branches read/diffed) | Deep. The single most technique-dense notebook in the corpus; peer branches add STL decomposition, richer rolling-statistics, and ACF-at-multiple-granularities, but also show the corpus's clearest anti-pattern (imputation-before-justification circularity). |
| geospatial | none | No evidence. No notebook in the trawl scope touches coordinates, maps, or spatial joins; not represented anywhere in `all-assignments`. |
| text/NLP | A7P1 (all 4 branches read/diffed) | Deep. Strong maintainer sequence (audited cleaning, stemmer bake-off, BoW/TF-IDF comparison); peer branches add corpus-wide artifact quantification, vocabulary-compression tracking, word clouds, bigram analysis, and independently converge on the same lemmatization POS-tagging fix. |
| images | A5P1 (thin, all branches), A5P2 (all 4 branches read/diffed) | Moderate-deep. A5P1 contributes almost nothing (transform mechanics, not exploration); A5P2 is the corpus's most process-explicit "EDA before augmentation" notebook, with peer branches adding resolution/aspect-ratio statistics and a structured multi-hypothesis augmentation table. |
| generic | every notebook, cross-cutting | Moderate. The `head/info/isna/describe/duplicated` first pass, the before/after-statistics validation pattern, the finding-to-action narrative closer, and the observation-hypothesis-expected-outcome template recur across tabular, time-series, and image notebooks and generalize past any one data type. |

## 5. Candidate for playbook — consolidated, by distinct technique

Verdicts already argued inline in Sections 2–3; this table is a flat
index for quick lookup. "Source" cites the branch/notebook where the
technique was first identified in this trawl.

| Technique | Topic | Source | Verdict | Why |
|---|---|---|---|---|
| Placeholder-category scan via `unique()` | tabular | maintainer A1P1 | yes | Catches sentinel missingness `isna()` misses |
| Z-score outlier filter, before/after describe+replot | tabular | maintainer A1P1 | yes | Makes an outlier-filter decision auditable |
| Column-pair redundancy check via `drop_duplicates()` | tabular | maintainer A1P1 | yes | Concrete test for duplicate-information columns |
| Boxplot-by-category as feature-validity check | tabular | maintainer A1P1 | yes | Catches a broken-feature data-quality bug, not just shape |
| Finding-to-action narrative closer | tabular, generic | maintainer A1P1 | yes | Closes the loop from EDA to feature engineering |
| Auto-profiling tool pointer (Facets/ydata/Sweetviz/dtale) | tabular, generic | maintainer + peer A1P1 | partial | Worth a pointer, not worth reproducing the tool survey |
| Three-way missing-value-treatment comparison | tabular, generic | canon A4P3 | yes | Compares fill/drop/impute explicitly rather than picking one blind |
| Mean±3·stddev outlier filter, before/after stats | tabular, generic | canon A4P3 | yes | Same validated pattern as the A1P1 z-score version, Spark-flavored |
| Four-condition missing-value scan (string+null) | tabular, generic | canon A4P3 | yes | Defensive against loosely-typed sources that encode missing as text |
| Per-stage structured "Observations" block | tabular, generic | peer A1P1 | yes | Better documentation cadence than one closing paragraph |
| Cramér's V for categorical-categorical association | tabular | peer + diff-only A1P1 | yes | Fills a real gap; two independent branches converged on it |
| Full-feature-sweep target-conditioned plots (not hand-picked) | tabular | peer A1P1 | yes | Systematic beats "features I happened to pick" |
| Ordinal encoding + trend line for ordinal features | tabular | peer A1P1 | yes | Treats ordinal data as ordinal, not nominal |
| Target-inclusive correlation matrix | tabular | diff-only A1P1 | yes | Direct feature-target linear-association view |
| Dtype recast before correlation (negative lesson) | tabular | diff-only A1P1 bug | yes | An un-recast ordinal code produced a spurious 0.66 correlation — recast first |
| Explicit 3-step feature-selection method | tabular | diff-only A1P1 | yes | More procedural than an ad hoc drop list |
| Full `date_range` reconstruction + longest-block detection | time-series | maintainer A6P1 | yes | Answers "is the time axis complete," distinct from "are there NaNs" |
| Multi-scale univariate plotting (span/year/week/day/YoY) | time-series | maintainer A6P1 | yes | Each scale yields a genuinely different, stated insight |
| Differencing to detrend for spurious correlation | time-series | maintainer A6P1 | partial | Core technique yes; the interactive lag slider is a nice-to-have |
| Moving-average family (SMA/EMA/TEMA/SMMA) | time-series | maintainer A6P1 | partial | SMA/EMA are standard; TEMA/SMMA are reference-table extras |
| ACF-justifies-imputation-window | time-series | maintainer A6P1 | yes | Strongest EDA-finding-to-cleaning-parameter chain in the corpus |
| Periodograms with frequency reference lines | time-series | maintainer A6P1 | yes | Genuinely useful frequency-domain complement to ACF, otherwise absent |
| Upsample-after-downsample information-loss demo | time-series | maintainer A6P1 | yes | Demonstrates the loss concretely rather than asserting it |
| STL decomposition | time-series | peer A6P1 | yes | Outlier-robust complement to classical decomposition |
| Richer rolling-stats dashboard (std/range/IQR/skew) | time-series | peer A6P1 | yes, as complement | Useful additions, but not a substitute for exponential smoothers |
| ACF-with-CI at multiple granularities, tied to persistence | time-series | diff-only A6P1 | yes | Formalizes the maintainer's own ACF-imputation reasoning |
| Multi-method upsampling comparison | time-series | diff-only A6P1 | yes | ffill/bfill/linear/cubic/nearest compared explicitly beats one default |
| Global impute-before-justify (negative lesson) | time-series | peer A6P1 bug | avoid | Circular: inflates the persistence stats used to justify the imputation |
| Skipping `date_range` reconstruction (negative lesson) | time-series | peer A6P1 | avoid | Misses wholly missing rows, not just missing values |
| Non-cyclic ordinal encoding fed into linear stats (negative lesson) | time-series | peer A6P1 bug | avoid | Contradicts the branch's own cyclical-encoding methodology |
| Stated-reasoning-not-reflected-in-code (negative lesson) | time-series | diff-only A6P1 | avoid | A documented imputation framework whose executed code ignores it |
| Synthetic-only decomposition demo (negative lesson) | time-series | diff-only A6P1 | avoid | Loses a real, dataset-specific finding for a toy example |
| Boolean "affected by artifact X" column | text/NLP | maintainer A7P1 | yes | Generalizes to auditing any suspected text contamination |
| Length-vs-label leakage check | text/NLP | maintainer A7P1 | yes | Cheap, text-specific check a plain `value_counts()` would miss |
| Per-step affected-row cleaning audit | text/NLP | maintainer A7P1 | yes | Turns "I cleaned the text" into an auditable, quantified claim |
| Positional word-diff comparator | text/NLP | maintainer A7P1 | yes | Generalizes to any two competing normalization outputs |
| Merged BoW-vs-TF-IDF single-document comparison | text/NLP | maintainer A7P1 | yes | Concretely shows frequency ≠ importance |
| Tokenizer-class packaging (clean+stem, one entry point) | text/NLP, generic | maintainer A7P1 | yes | Good practice regardless of the specific steps chosen |
| Corpus-wide regex artifact taxonomy in docstring | text/NLP | peer A7P1 | yes | Ties diagnostic percentage directly to the cleaning rationale |
| Vocabulary-size-by-stage comparison | text/NLP | peer A7P1 | yes | Cheap, concrete view of normalization's compression effect |
| Word clouds (per-stage, sentiment-split, BoW-vs-TF-IDF) | text/NLP | peer A7P1 | yes | Sentiment-split cloud is a genuinely new visual technique |
| Bigram frequency analysis | text/NLP | peer A7P1 | yes | Tests the "BoW loses order" claim with real numbers |
| POS-tagged lemmatization fix | text/NLP | diff-only A7P1 | yes | Two branches independently found the same real bug |
| Punctuation-frequency-by-label analysis | text/NLP | diff-only A7P1 | yes | A genuine new insight (question marks skew negative) |
| VADER sentiment-score histogram by label | text/NLP | diff-only A7P1 | yes | Cheap lexicon-based cross-check against the label |
| Duplicates detected but never dropped (negative lesson) | text/NLP | peer A7P1 | avoid | Finding never acted on; leaves a leakage risk open |
| Missing text-length EDA (negative lesson, omission) | text/NLP | peer A7P1 | avoid | Whole canon sub-step skipped outright |
| Apostrophe-stripping regex bug (negative lesson) | text/NLP | peer A7P1 bug | avoid | Silently collapses sentiment-critical negations |
| A5P1 transform-mechanics-as-EDA | images | maintainer A5P1 | no | Not enough dataset-level content to generalize into a playbook |
| Per-class mean-channel-value check | images | maintainer A5P2 | yes | Cheap, general "is colour a usable signal" test |
| Seeded `Generator`-based sampling | images, generic | maintainer A5P2 | yes | Reproducible and composable, unlike global `random` state |
| Fixed-question-list-per-sample-row template | images | maintainer A5P2 | yes | Reusable image-EDA checklist, turns a skim into a structured record |
| Observation-hypothesis-expected-outcome augmentation template | images, generic | maintainer A5P2 | yes | Falsifiable augmentation choice, stronger than "try some augmentations" |
| Corpus-wide resolution/aspect-ratio/channel/format scan | images | peer A5P2 | yes | Directly motivates a later crop/resize augmentation choice |
| Five-hypothesis structured augmentation table | images | peer A5P2 | yes | Clearer, more scalable than one-technique-at-a-time |
| Min/max-ratio-driven imbalance decision framework | images | diff-only A5P2 | yes | Closes the finding-to-action loop a bare ratio leaves open |
| Corrupted-image/channel-count audit | images | diff-only A5P2 | yes | Cheap defensive check absent from the maintainer's branch |
| Dual Sobel kernel (horizontal+vertical) | images | diff-only A5P1 | yes | More complete edge-detection demo at negligible extra cost |
| Global `random.seed()` for sampling (negative lesson) | images | peer A5P2 | avoid | Mutates global RNG state instead of a scoped `Generator` |
| Single-image-per-transform display (negative lesson) | images | diff-only A5P1 | avoid | Loses the comparative view that makes a parameter's effect legible |
| Inaccurate imbalance read, no corrective action (negative lesson) | images | diff-only A5P2 | avoid | Worse than not measuring imbalance: wrong conclusion, no consequence |
