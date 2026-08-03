# EDA Playbook — Time Series

Observations indexed by time, where order carries information. Load with
[playbook-generic.md](playbook-generic.md) (first-pass ritual, cleaning
workflow, leakage rules) and
[playbook-stat-tests.md](playbook-stat-tests.md).

`[external]` marks published practice adopted here but not yet exercised
in a shipped analysis.

## 1. Is the time axis complete

Distinct from "are there missing values", and asked first. A `NaN` scan
on an existing index cannot see wholly absent rows.

- Build the expected grid with `pd.date_range(start, end, freq=...)` and
  left-merge the data onto it. Group the resulting null rows by
  year/month/day to list which periods are absent.
- Find the longest unbroken run, and scope persistence analysis to it:

```
mask = df["value"].notna().astype(int)
df["block"] = (mask.diff(1) != 0).cumsum()
valid_blocks = df[mask == 1].groupby("block").size()
```

- Record the gap inventory before touching it. Every later imputation
  decision is argued against this list.

## 2. Step 0 — is it forecastable at all

Screen before choosing a model family, so that a near-random series is
not handed to progressively larger models.

| Measure | Reading |
|---|---|
| Permutation entropy | 0 predictable, 1 random; model-free |
| Spectral predictability | below 0.2 indicates low forecastability |
| Largest Lyapunov exponent | above 1.0 is low, needs 100+ points |
| Sample / approximate entropy | correlates with out-of-sample error |

A near-zero intrinsic predictability score is a finding that ends the
modelling question, and is recorded as such.

## 3. Multi-scale univariate plotting

Plot the same series at five scales, each answering a different
question, each with its own observation block:

- **Full span** — usually too dense to read, and that is a stated
  negative finding, not a wasted cell.
- **Aggregated (monthly)** — trend and annual seasonality.
- **One year** — within-year shape.
- **One week and one day** — intraday and weekday cycles.
- **Year on year**, aligned by day of year with `hue="year"` — regime
  shifts and level changes between years.

Histograms are still worth drawing, with the caveat stated that a
frequency histogram cannot show temporal structure. A KDE hued by month
shows distribution shift across the year.

## 4. Stationarity

- **Rolling mean and rolling standard deviation** over a fixed window,
  plus a first-half against second-half comparison of mean and variance
  `[external]`. Cheap, visual, and enough to decide whether to
  difference.
- Confirm with **ADF** and **KPSS**. They test opposite null hypotheses;
  agreement is the useful signal.
- A rolling-statistics dashboard (std, min/max range, median with IQR,
  rolling skewness) extends the same read to variance and shape drift.

## 5. Decomposition

| Situation | Method |
|---|---|
| Structural understanding, stable seasonality | Classical (moving average) |
| Noisy or outlier-heavy periodic series | STL with `robust=True` |
| Slowly evolving seasonality | STL |
| Multiple or non-integer seasonal periods | MSTL, TBATS |

Classical decomposition is outlier-sensitive and assumes constant
seasonality; STL is LOESS-based, robust when asked, and needs no
stationarity. Decomposition is complementary, not required, and is often
unhelpful on high-frequency or irregular series.

Additive against multiplicative is a choice to state: run both and read
which leaves a structureless residual. A multiplicative fit needs a
positive series, so shift before dividing.

## 6. Dependence structure

- **ACF** answers "does this series' past predict its future"; plot it
  beside the matching univariate plot so the shape and the correlogram
  are read together, with confidence intervals shown.
- **PACF, not ACF, selects lag features.** ACF at lag 2 may be entirely
  decayed lag-1 information; PACF isolates what each lag adds.
- Both measure **linear** dependence only. Check lag plots (series
  against its own lag, annotated with the correlation) or mutual
  information for nonlinear structure before fixing the lag set.
- **Periodograms** with vertical reference lines at daily, weekly, and
  monthly frequencies name which cycles are worth encoding as features.
- Cross-correlation detects lead-lag between two series; state the sign
  convention explicitly (k > 0 meaning x leads y).

## 7. Correlation between series

Independent-observation assumptions do not hold, so a raw correlation
heatmap between two trending series is close to meaningless. Attach the
caveat at the correlation step, then first-difference both series
(`d(t) = obs(t) - obs(t-1)`) and re-read. Show the raw and differenced
scatters side by side; the collapse is the demonstration.

Cyclic features (wind direction, hour of day, month) are encoded as
sin/cos pairs before entering any linear statistic. An arbitrary integer
map has no wraparound, and feeding it to Pearson, ACF, or a periodogram
produces confident nonsense.

## 8. Outliers

- Gate the method on normality: z-score (3 sigma) requires it, IQR is
  distribution-free and preferred for skewed or heavy-tailed series.
- **Verify against domain knowledge.** Does the spike make business
  sense, and was there an event?
- **Model the spike, do not remove it.** In forecasting, shocks and
  regime shifts are often the signal; a dummy variable keeps the
  information a filter would delete.

## 9. Missing data

- **Trap: impute before justify.** A forward-filled series is by
  construction maximally autocorrelated, so ACF, periodogram, and
  persistence statistics computed on a globally filled frame partly
  measure the imputation. Correct order: reason from ACF on the real
  gaps (using the longest clean block from step 1), pick the window from
  that persistence reading, then impute.
- The chain to record: ACF decay length → imputation window → method.
  High persistence supports forward or backward fill; low persistence
  supports a mean or a centred rolling mean over the ACF window.
- Compare methods rather than defaulting: ffill, bfill, linear, cubic,
  nearest, and a centred rolling mean plotted over the same gap.
- Re-run the step-1 gap check after imputing, which catches gaps the
  chosen method could not fill.

## 10. Resampling

- Downsampling (`resample("6H").mean()`) changes the frequency;
  smoothing changes the values at the same frequency. They are different
  operations and are labelled as such.
- Demonstrate the round trip rather than asserting it: downsample, then
  upsample back with `asfreq()` plus `interpolate(method="time")`, and
  plot against the original. The visible gap is the information cost.

## 11. Alignment before modelling

- **Trap: target alignment.** `[external]` Every feature at time t must
  be built from values at t-1 or earlier. A feature using t leaks the
  present and is the most common bug in time-series feature
  engineering.
- Validation is temporal: walk-forward with an expanding or sliding
  window, never random k-fold. Hold out at least one full seasonal
  cycle.
- Establish persistence and seasonal-naive baselines during EDA. A model
  that loses to seasonal-naive is a bug report, not a result.
