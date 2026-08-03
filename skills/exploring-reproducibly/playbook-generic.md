# EDA Playbook — Generic Spine

The shared base for every topic playbook. Load it with any EDA work,
together with [playbook-stat-tests.md](playbook-stat-tests.md) and the
topic playbook matching the data at hand. Prose and observation-cell
format follow [analysis-style.md](analysis-style.md).

`[external]` marks published practice adopted here but not yet exercised
in a shipped analysis. Evaluate it against the data before relying on it.

## The five stages

Run them in order. A stage skipped is recorded as skipped, with the
reason.

1. **Preliminary** — shape, dtypes, missingness, duplicates.
2. **Univariate** — counts for categorical, histograms for continuous.
3. **Bivariate** — feature against feature, and every feature against
   the target.
4. **Outlier** — detect, classify (error, genuine, placeholder), treat.
5. **Correlation** — association structure, with the assumptions of the
   chosen coefficient stated.

## First-pass ritual

Before any plot: `df.head()` → `df.info()` → `df.isna().sum()` →
`df.describe().T` → `df.duplicated().sum()` → `df[df.duplicated(keep=
False)]` to see what the duplicates are before dropping them.

Then two scans `isna()` cannot do:

- **Placeholder categories** — `df[col].unique()` on every object
  column. Sentinels such as `"?"`, `"Not in universe"`, `"Do not know"`
  are semantically missing and count as present.
- **Placeholder numerics** — a maximum pinned at `9999` or `99999` in a
  right-skewed column is a ceiling code, not an observation.

For loosely typed sources count missingness over four conditions in one
pass: true null, `NaN`, empty string, and the literals `"None"`/`"NULL"`.

## Profiling frame

One table answers most encoding and drop decisions immediately:

```
pd.DataFrame({
    "missing": df.isna().sum(),
    "n_unique": df.nunique(),
    "example": df.iloc[0],
})
```

## Cleaning workflow

Eight steps, each logged with before/after counts.

1. Understand the data — expected ranges, units, data dictionary.
2. Standardise structure — column names, dtypes, units, encodings.
3. Handle missing data — placeholders first, then drop, impute, or keep.
4. Remove or flag duplicates — exact by rule, near duplicates case by
   case.
5. Drop irrelevant columns and rows.
6. Correct inconsistent values — spellings, typos, ranges, cross field
   rules such as `start_date <= end_date`.
7. Detect and treat outliers — correct if error, keep if genuine, cap
   only for modelling.
8. Final consistency check — no placeholders left, dtypes re-checked,
   clean copy saved, cleaning log written.

Dropping is the last resort: check whether another column infers the
missing one, and compare three treatments (constant fill, row drop,
fitted imputer) rather than defaulting to one.

## Leakage rules

- **Split first, then scale.** Fitting a scaler on the full frame leaks
  test statistics into training and produces optimistic estimates. The
  same rule binds every stateful transform: encoders, imputers, target
  encoding.
- **Drop post-hoc features.** A column unavailable at prediction time is
  information from the future. Name each one and drop it during EDA.
- **Class balance gates the split.** Imbalance found in EDA means the
  split is stratified.

## Before/after validation

Any filter, imputation, or transform is validated the same way: rerun
`describe()` and redraw the same plot on the changed frame, and state
what moved. An outlier filter that does not shift the reported maximum
did not do what it claimed.

## Per-stage observation blocks

Close every stage with its own `Observations & Findings:` block in the
format from [analysis-style.md](analysis-style.md), written at
observation time. One synthesis paragraph at the end of the notebook is
a reconstruction and loses the per-stage reasoning.

## Finding to action

**Trap: findings without actions.** Imbalance measured and never acted
on, duplicates counted and never dropped, an outlier flagged and left in
place. This is worse than not measuring: the number reads as handled.

Every measured finding ends in one recorded decision — **drop**,
**keep**, **transform**, or **investigate** — naming the column and the
consequence. A dimension measured once and set aside says so.

## Auto-profiling tools

One pass with a target-conditioned profiler (the target passed as the
comparison feature) beats a general-purpose data viewer, because it
ranks by relevance to the question. Its output is a checklist to verify,
never the analysis.
