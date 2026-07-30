# Analysis Style Contract

Leo's voice for notebooks, findings docs, and analysis reports. Load when
writing any analysis prose, observation cell, or report section.
Evidence base: docs/research/2026-07-30-analysis-style-micron.md and
docs/research/2026-07-30-analysis-style-mindef.md.

## Prose rules

1. **Dashes are structural, never prose.** Allowed: a dash as a separator
   in headings ("## 2.1 Bar Chart — Target Distribution") and in
   name/description pairs inside tables or trees. Banned: em or en dashes
   as clause joins inside sentences. Dash-heavy prose reads as
   AI-generated, which is exactly the impression to avoid.
2. **De-hyphenate compound modifiers in analysis text.** Write "chi
   square test", "one parameter model", "zero truncated", "5 fold
   stratified cross validation", "non negative counts". Hyphens stay only
   where the unhyphenated form is a different word or unreadable.
3. Spell out "percent" in observation bullets. The % sign is fine inside
   tables and figures.
4. Verbal hedges over spurious precision: "about 2.7", "roughly 9 times".
   Exact numbers only when the exactness matters.
5. Backticks around every column name, file path, and parameter. British
   spelling in prose. Bold only the load-bearing number or term, never a
   whole sentence.
6. First person plural, used sparingly, for judgments ("we compare", "the
   model we ship"). Method statements stay impersonal.

## Observation cells

After every code cell whose output says something, add exactly one
markdown cell:

```
Observations & Findings:

* Mean about 2.7, variance about 24, so the variance is roughly 9 times
  the mean. The data are overdispersed
* Half the agents close a single sale
* The maximum is 255, far above the mean, so the tail is heavy
```

Rules:
- Plain text header with the colon, not bold, not a heading.
- 2 to 4 bullets. More means the cell is doing two jobs, split the code.
- Each bullet is quantity plus interpretation, joined by "so" where there
  is a consequence. No terminal periods.
- Every bullet lands on a decision or a flagged question. A fact with no
  consequence does not earn a bullet.
- Terse is fine when there is nothing to say: "No duplicates to settle".

## Findings cells (model training variant)

After each model's evaluation block, one cell headed bare `Findings`,
grouped by the artifacts just produced (Metric report, Confusion matrix,
PR curves, Feature importance), closing with a one line `Takeaway:` that
states what this model result means for selection.

## Decision tables before code

Commit the reasoning before the result exists, as a two column table:
"Consideration | Decision" for methodology, "Metric | Why it is here"
before computing metrics, "Feature of the data | What it implies" for
family or approach choices. The rationale cannot be retrofitted if it is
written first.

## Structure

- Headings numbered and hierarchical: `# N. Title`, `## N.M Title`. A
  `---` rule in its own cell before every top level section.
- The notebook opens with scope and provenance: task restated, data
  source linked, `Scope:` bullets naming filters and keys.
- The notebook closes with `Limitations` (or `Named assumptions &
  limitations`). Always.
- Negative results are kept on the record, never deleted: a "Tested &
  Rejected" appendix for experiments, "checked once here, then set aside"
  for dimensions measured and dismissed.
- Every notebook section that produces a modelling input states it, so
  the closing summary can specify the downstream pipeline.

## Charts

- Titles state the takeaway, not the variables ("Pay explains Group X's
  drift, not Group Y's"). Alternatively leave figures untitled and let
  the markdown carry it. Never a title that merely names the axes.
- Single hue for the data, one accent for reference or comparison.
  Value labels on bars. Spines stripped top and right. Reference lines
  annotated with their meaning.
- Save figures deliberately (`dpi=130` to `150`, `bbox_inches="tight"`),
  never rely on notebook state.

## Reports and READMEs

- Per section template: restating paragraph, Deliverable, Data, Notebook
  structure table, Result, Running it.
- Every preprocessing choice framed as "X over Y" plus the reason.
- Worked example after every formula.
- A metric's blind spot is named in the same breath as its number ("with
  a single row, F1 can only be 0 or 1, so these measure nothing").
