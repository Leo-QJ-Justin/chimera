# EDA Playbook — Tabular

Feature-and-row data with a target column. Load with
[playbook-generic.md](playbook-generic.md) (five stages, first-pass
ritual, cleaning workflow, leakage rules) and
[playbook-stat-tests.md](playbook-stat-tests.md) (group comparisons,
Cramer's V, chi square).

`[external]` marks published practice adopted here but not yet exercised
in a shipped analysis.

## 1. Structure and dtypes

- Run the generic first-pass ritual, including the placeholder-category
  scan. Coded categoricals are the common trap it surfaces.
- **Recast coded categoricals before anything numeric.** Columns such as
  `industry_recode`, `occupation_recode`, or a benefits flag arrive as
  integers but are labels, so `describe()` reports a meaningless mean.
  Cast them to `object` or `category` in the cleaning step.
- **Trap: un-recast codes in a correlation frame.** An ordinal code left
  numeric produces a confident spurious correlation (0.66 against age in
  one observed case) that survives into feature selection. Correct
  order: recast dtypes, then build the correlation frame, then read it.
- Record cardinality per categorical column. Cardinality plus "is there
  a natural order" is what decides one-hot against ordinal encoding
  later; high-cardinality columns are candidates for collapsing into
  coarser groups or a derived boolean flag.

## 2. Univariate

- One paginated histogram grid over every numeric column
  (`kde=True`, fixed columns per page, leftover axes hidden). Sweep
  everything; do not hand-pick.
- One bar chart per categorical column on
  `value_counts(normalize=True)`, read for near-constant columns and for
  categories thin enough to merge before encoding.
- Skew and near-zero-variance screens on `describe().T` are cheaper than
  reading the grid: flag `|skew| > 2` and `std / (max - min) < 0.01`.

## 3. Bivariate and target-conditioned

- **Sweep all features against the target, not a chosen few.** Boxplot
  every numeric feature by target class; stacked proportion bars
  (`pd.crosstab(..., normalize="index")`) for every categorical, split
  into low-cardinality and high-cardinality panels.
- **Boxplot by category is a validity check, not just a shape check.**
  A wage column reading zero for full-time workers contradicts the
  column's stated meaning, and that finding drops the column rather than
  imputing it.
- **Column-pair redundancy** — `df[[a, b]].drop_duplicates()` returning
  as many rows as `b` has categories proves `a` is `b` at finer
  granularity. Cheaper and more decisive than eyeballing a heatmap.
- **Ordinal features stay ordinal.** Encode against an explicit rank
  list, then boxplot and plot the group mean trend across levels. A flat
  or non-monotonic trend is itself the finding.

## 4. Association measures

- **Pearson** assumes continuous, linear, roughly normal, homoscedastic
  data and is outlier-sensitive. **Spearman** needs only monotonicity,
  works on ranks, loses magnitude information, is sensitive to ties, and
  underrepresents meaningful outliers precisely because it is robust to
  them. Run both and state which one the conclusion rests on.
- Include the target in the correlation frame. The feature-target column
  is the one being read most.
- **Cramer's V** for categorical against categorical, which correlation
  cannot measure at all:

```
def cramers_v(x, y):
    table = pd.crosstab(x, y)
    chi2 = scipy.stats.chi2_contingency(table)[0]
    n = table.to_numpy().sum()
    return np.sqrt(chi2 / (n * (min(table.shape) - 1)))
```

- **Mutual information** `[external]` as the nonlinear filter: a feature
  can have zero correlation and high mutual information when the
  relationship is quadratic or periodic. Binning count is the knob, too
  few loses structure and too many adds noise.

## 5. Feature selection

Three steps per candidate, recorded as a decision:

1. Check its distribution (near-constant, degenerate, placeholder-laden).
2. Check its predictive power against the target (boxplot, stacked
   proportion bar, mutual information rank).
3. State the drop, keep, or transform decision with the reason.

- A high-correlation screen (`|rho| > 0.9` on the upper triangle) lists
  redundant pairs; keep one per pair and say which and why.
- **Permutation importance** `[external]` corrects tree importance,
  which is biased toward high-cardinality features (a random ID column
  looks important because it splits every sample). Boundary: it needs a
  fitted model, so it is a model-diagnostic step, not an EDA step. Reach
  for it after a first model exists, not before.

## 6. Outliers and anomalies

- Classify before treating: point, contextual, or collective.
- **Z-score** (`|z| < 3`) assumes approximate normality and is
  univariate. **IQR** is distribution-free and preferred for skewed
  columns. Validate either with the generic before/after
  describe-then-replot pattern.
- **Isolation Forest / LOF** `[external]` for multivariate and
  multimodal cases, where a z-score screen per column cannot see a
  joint anomaly. LOF finds local density anomalies; Isolation Forest
  scales better in high dimensions.

## 7. Imbalance

| Degree | Minority class share |
|---|---|
| Mild | 20 to 40 percent |
| Moderate | 1 to 20 percent |
| Extreme | under 1 percent |

Guideline, not a rule. The degree feeds three decisions, all recorded in
the EDA close: stratified split, metric choice, and whether class
weighting is on the table for training.

- Under imbalance, prefer the precision-recall curve over ROC: ROC
  includes true negatives and flatters a model that never predicts the
  minority class.
- **AUPRC, MCC, and Precision@k** `[external]` as the reporting metrics
  for rare-event work. A random classifier's AUPRC equals the positive
  rate, not 0.5, so quote the baseline beside the number.
- Do not adopt synthetic minority oversampling as a default EDA
  recommendation. Interpolating new minority points from a handful of
  real samples fabricates combinations that were never observed.
- A missing-value indicator column is justified only when EDA shows the
  missingness itself carries signal (for example, missingness
  concentrated in one class). Tie an indicator to a specific finding,
  never apply one generically.

## 8. Closing the notebook

Group every feature into drop, re-aggregate, or redundant-pick-one, name
the imbalance response, and state the transforms the training pipeline
inherits. The EDA ends by specifying the pipeline it feeds.
