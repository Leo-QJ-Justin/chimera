# EDA Playbook — Statistical Tests

The shared appendix for every topic playbook. Reach for it the moment an
EDA finding turns into "is this difference real". Load it alongside
[playbook-generic.md](playbook-generic.md).

## Three questions first

1. **What am I comparing** — one group against a known value, two
   independent groups, the same group twice, or three or more groups.
2. **Is the data approximately normal** — QQ plot plus Shapiro-Wilk, or
   the central limit theorem where n is large.
3. **Do I know the population variance** — almost always no, so t over Z
   in practice.

Direction (one sided or two sided) is decided before seeing the data.
Choosing it afterwards is a hypothesis fitted to the result.

## Which test

```
Is your outcome variable continuous or categorical?
│
├── Categorical → chi-square tests (below)
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

## Normality gate

Shapiro-Wilk chooses the path: `p > 0.05` supports a parametric test,
`p < 0.05` sends you to the non-parametric equivalent.
Read it beside a QQ plot, because at large n Shapiro-Wilk rejects on
deviations too small to matter.

## Variance gate

Levene's test decides between the two-sample t variants: `p > 0.05` for
equal variances gives the Pooled t-test, `p < 0.05` gives Welch's.
Welch is the safer default when the test is ambiguous.

## Parametric and non-parametric equivalents

| Question | Parametric | Non-parametric |
|---|---|---|
| One group vs a known value | One-sample t | Sign test |
| Same group, two time points | Paired t | Wilcoxon signed-rank |
| Two independent groups | Independent two-sample t | Mann-Whitney U |
| Three or more groups | One-way ANOVA | Kruskal-Wallis |

## Categorical outcomes

- **Goodness of fit** — one categorical variable against a hypothesised
  distribution.
- **Test of independence** — two categorical variables, contingency
  table, `chi2_contingency`.
- Report **Cramer's V** in the same breath: chi square says an
  association exists, V says how large it is.
- At large n a chi square test rejects almost any model. Compare the
  sizes of the statistics rather than the p values, and lead with the
  effect size.

## Three or more groups

- One-way ANOVA is gated on three assumptions: independence, normality
  (Shapiro-Wilk per group), and homogeneity of variance (Levene). A
  failure on normality or homogeneity sends you to Kruskal-Wallis.
- ANOVA says some group differs. Only the post hoc names which.
- **Tukey-Kramer is the default post hoc.** It handles unequal group
  sizes; Bonferroni is overly strict and has lower power.

## Recording the result

Report the statistic, the p value, the effect size, and the decision the
result changes. A test that changes no decision does not belong in the
notebook.
