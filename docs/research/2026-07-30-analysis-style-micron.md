# Leo's Analysis Style — Micron Assessment Mining Report

> Research artifact for chimera. Mined 2026-07-30 from the Micron technical
> assessment (tabular multi-class classification, severe imbalance; stack:
> uv, pandas, seaborn, sklearn, lightgbm, torch, optuna). Purpose: evidence
> base for codifying Leo's analysis style and EDA/training process into
> chimera skills. Sibling: [Mindef report](2026-07-30-analysis-style-mindef.md).

## EDA processing steps, exact order (eda.ipynb)

Cell 0 is always imports + `sns.set_style('whitegrid')`, no markdown before it.

1. §1 Preliminary Data Exploration: 1.1 Loading (relative path one-liner) →
   1.2 Peeking (`df.head()`) → 1.3 Summarize the Structure (`df.info()` —
   no separate shape/dtypes cells) → 1.4 Missing Values (`df.isna().sum()`)
   → **1.4.1 Missingness vs Target** (signature move: missingness treated
   as candidate feature, not nuisance; grouped barplot excluding the
   majority class) → 1.5 Descriptive Statistics (`describe().T` + three
   robust screens: relative near-zero variance `std/(max-min) < 0.01`,
   skew `|skew| > 2`, scale-spread table) → 1.6 Duplicates → 1.7 Dataset
   Preparation (**cleaning happens mid-EDA**, numbered in-code steps with
   before/after counts).
2. §2 Univariate: 2.1 target countplot with annotated bars + count/% table
   → 2.2 paginated histogram grids (12/page, 3x4, `kde=True`, hidden
   leftover axes, "Page N of M" suptitles).
3. §3 Bivariate: 3.1 `mutual_info_classif` ranking → top-8 boxplots by
   class → 3.2 paginated per-class KDE overlays (indicators excluded).
4. §4 Correlation: Spearman |rho| > 0.9 upper-triangle screen → list
   offending pairs → drop cell reprinting shape.
5. §5 Summary & Pipeline Design: markdown-only close — final-dataset table
   + **Pipeline Decisions** (imbalance, transforms, scaling, validation,
   models). The EDA ends by specifying the training pipeline.

Idioms: `feature_cols` recomputed after every column change; robust
choices always (Spearman, median, RobustScaler, relative screens);
`random_state=42` on everything stochastic incl. MI; every plot ends
`plt.tight_layout(); plt.show()`; named colors (steelblue/tomato/Set2);
comments state the REASON not the action.

## Training workflow, exact order (training.ipynb)

1. Opens with a ~1,200-word methodology essay BEFORE any code: model
   selection table, "Why cross-validation? / Why stratified?" bolded
   question prompts, imbalance strategy, **Primary metric: Macro F1**,
   diagnostic plots pre-explained.
2. Setup: `sys.path.insert(0, '..')`, imports from `src.pipelines.*`,
   logging basicConfig.
3. Clean → stratified 80/20 split on cleaned-but-untransformed data →
   `fit_transform(train)` / `transform(test)` with leakage comments
   ("fit preprocessing on TRAIN ONLY").
4. Strategy switch as ALL-CAPS constant (`SMOTE_RATIO = 0.0`).
5. Reusable `run_cv` harness refitting a fresh pipeline per fold
   (StratifiedKFold 5, shuffle, seed).
6. Per-model identical 6-step template x3 (LogReg → LightGBM → MLP):
   Optuna tune (unequal budgets, justified: 10/50/20 trials) → CV on tuned
   config → test evaluate + classification_report → row-normalised
   confusion matrix → (LightGBM) gain importance → PR curves → `Findings`
   markdown cell.
7. §6 Model Comparison: mean±std CV column, test metrics; **selection on
   CV, never test** ("so the test column remains an honest held-out
   estimate"); programmatic `best_by_cv`.
8. §7 Appendix — Hybrid SMOTE: **Tested & Rejected** — controlled A/B
   through the same harness, bolded verdict cell, knob kept in codebase
   for reproducibility.

No SHAP, no calibration; interpretation via gain importance + MI + KDE
cross-referencing.

## Markdown style (verbatim evidence)

**Dominant EDA pattern — `**Observations & Findings:**`** (12x): bolded
header with colon, immediately after the code cell it reads, `*` bullets.
Representative:

> **Observations & Findings:**
>
> * Features 40, 69, 75
>     - Missingness falls entirely in class 0
>     - Missing at random w.r.t. target → median impute, no indicator needed
> * Feature 80
>     - All 56 missing rows are class 2 (95% of class 2's 59 samples)
>     - Missingness is almost a perfect class 2 label → add feat_80_is_missing indicator + median impute
>     - This indicator will likely be one of the strongest features in the model

> * **Class 2 near-perfect isolators** — Features 9, 25, 40, 47, 73, 82,
>   98, 108, 112 each show a Class 2 mode fully separated from all other
>   classes

Terse when nothing to say: "No duplicates to settle".

**Training variant — bare `Findings`** (3x): no bold, artifact-named
groups matching the plots above (Metric report / Confusion matrix (errors)
/ PR curves / Feature importance), closing `Takeaway:` one-liner.

> Takeaway: a linear model ranks class 2 but can't separate the rest; sets
> the floor at 0.37.

Verdict style: "It is a data problem and not a model problem."
Rejection style: "**Conclusion — we do not adopt SMOTE.** … Oversampling
would only compromise the model we actually ship, in exchange for
fabricating synthetic minority points from as few as 23 real samples."

**Characterization:**
- Numbered hierarchical headings; section titles add artifact type with an
  em dash ("## 2.1 Bar Chart — Target Distribution"); `---` rules between
  top-level sections.
- Cells interpret, never merely label; every observation terminates in a
  decision.
- First-person plural; hedged forward-looking language ("likely", "further
  analysis required", "candidates for removal").
- Bullets 8-25 words, quantified ALWAYS (counts, percentages, thresholds,
  feature IDs enumerated); bold lead noun phrase + em dash + implication.
- `→` as the decision arrow; `~`/`≈` approximations; `w.r.t.`; backticks
  on identifiers; British -ise mixed with American -ize.
- **Punctuation in THIS corpus:** em dash (—) as the signature clause
  join (43 uses in eda.ipynb md); en dash for ranges (`classes 1–4`);
  compound modifiers hyphenated freely (`near-perfect`, `row-normalised`).
  NOTE: this CONTRADICTS the Mindef Section 2 notebooks and Leo's stated
  no-hyphen preference — see the Mindef report §hyphens for the split.
  Never ` - ` as clause separator, never `--`.
- Negative results documented in a "Tested & Rejected" appendix, not
  deleted.
- Cross-referencing constant: "consistent with the high skew count from
  section 1.5", "cross-referencing our EDA we know 25 to be a strong
  predictor of class 2"; EDA findings hard-coded into src as constants
  with comments citing the EDA section (`# (EDA 1.4.1)`), plus a
  regeneration escape hatch comment.

## Structure conventions

- Repo: `main.py` (thin entry) / `data/raw` (committed) vs
  `data/processed` (gitignored) / `notebooks/` (eda.ipynb, training.ipynb
  — lowercase single words, no numeric prefixes) / `src/pipelines/` with
  `classes/` (OO estimators, one file per model, common ABC) vs `modules/`
  (stateless functions: evaluation, resampling).
- src vs notebook: production/reusable code in src (incl. plot functions);
  notebook keeps narrative, run_cv composition, comparison table, A/B.
- Leakage as architecture: stateless `clean()` pre-split vs stateful
  `fit_transform/transform` train-only; `transform()` raises if unfitted.
- Seed: single `random_seed=42` parameter threaded everywhere;
  `get_config()` round-trips so `type(clf)(**clf.get_config())` rebuilds a
  fresh twin for CV-on-tuned-config.
- logging in src (`%(levelname)s | %(message)s`), print in notebooks;
  Google-style docstrings everywhere incl. Attributes blocks; PEP 604
  hints; numbered section banner comments matching README pipeline steps.

## README style

Order: title — Q1 → Name/Email → framing para → Repository Structure
(annotated bullet tree, ` – ` en dash name→description separator) →
Executing the Pipeline → Pipeline Flow (per step: Script / Action / Key
steps with implementing file paths) → EDA Summary (numbered, quantified) →
Preprocessing rationale (every choice "X over Y" + reason) → Feature
Processing → Model Choices → Model Evaluation (LaTeX macro-F1 definition;
selection-integrity statement repeated) → SMOTE Tested & Rejected →
Limitations & Future Work. `1)` numbering for prose sections; hard-wrapped
~95 chars; polish gradient runs high→low down the document.
