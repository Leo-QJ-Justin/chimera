# EDA Playbook — Text

Free-text corpora, labelled or unlabelled. Load with
[playbook-generic.md](playbook-generic.md) (first-pass ritual, cleaning
workflow, leakage rules) and
[playbook-stat-tests.md](playbook-stat-tests.md).

`[external]` marks published practice adopted here but not yet exercised
in a shipped analysis.

## The sequence

1. Define the corpus — tokenisation and vocabulary are scoped to it, and
   subsets by label or source enable drift comparison.
2. Profile length and duplicates.
3. Quantify artefacts before cleaning any of them.
4. Clean and normalise, auditing each step.
5. Filter by language.
6. Tokenise and compute per-document lexical metrics.
7. Track vocabulary size by stage.
8. Compare competing normalisations empirically.
9. Visualise corpus distributions.
10. Vectorise and inspect one document.
11. Score sentiment and compare it against the labels.
12. Package the pipeline and freeze its behaviour.

## 1. Length, duplicates, labels

- `text.str.len().describe()` plus a histogram. Read the extreme tail
  directly (`textwrap.fill` on the longest document) rather than
  trusting the summary.
- `duplicated().sum()` **and** `drop_duplicates()`. A duplicate counted
  and left in place is a train/test leakage path.
- Label distribution decides whether weighting or stratification is
  needed, per the imbalance table in `playbook-tabular.md`.
- **Length against label** is a text-specific leakage check: bin the
  length and draw a stacked label-distribution bar. If length alone
  predicts the label, a classifier will learn length.

## 2. Artefact taxonomy, quantified

Scan for each artefact class independently with `.str.contains` and
report the share of the corpus it touches: HTML tags, HTML entities,
URLs, mentions and hashtags, digit runs, backslash or dash runs,
non-English characters.

Carry the percentages into the cleaning function's docstring, so the
quantification travels with the code that acts on it. A cleaning step
touching under one percent of the corpus needs a stated reason to exist.

## 3. Audited cleaning

Order: HTML → URLs → lowercase → accent strip
(`unicodedata.normalize("NFKD", ...)`) → contraction expansion →
mentions and hashtags → digits → special characters → punctuation.

Punctuation removal is tested, not assumed: punctuation carries
sentiment information.

Track every step's effect per record rather than asserting the corpus
was cleaned:

```
df["step1_no_html"] = df["original_text"].apply(remove_html_tags)
df["affected_html"] = df["original_text"] != df["step1_no_html"]
```

Sum the `affected_*` flags per row into a "how many steps touched this
document" histogram. This turns "the text was cleaned" into an auditable
count.

**Defect to avoid: apostrophe-stripping regexes.**
`re.sub(r"[^a-zA-Z\s]", " ", text)` turns `"don't"` into `"don t"`, and a
downstream short-token filter then drops the `"t"`, silently collapsing
negations into their opposites. Expand contractions before stripping,
and keep the apostrophe out of the character class.

## 4. Language filtering

`langdetect` with `DetectorFactory.seed = 0` for reproducibility, then
filter to the target language and plot the distribution of what was
removed. Mixed-language documents distort both metrics and tokenisation.

## 5. Lexical metrics

Per document: character count (catches truncation), token count,
vocabulary size, and type-token ratio. TTR falls with length, so use
log-TTR or MTLD when comparing documents of unequal length. Corpus
level: total tokens, vocabulary size, top-n words, and a three-panel
histogram of token count, vocabulary size, and TTR split by label.

## 6. Normalisation bake-off

- Compare stemmers and lemmatisers empirically on the same sample, timed
  and inspected, rather than choosing from a pros-and-cons table.
- **Positional word-diff comparator** — print only the token positions
  where two normalised outputs disagree. It reads far faster than
  diffing full strings and generalises to any two competing outputs
  (stemmer against stemmer, cleaning version A against B).
- **Trap: POS-less lemmatisation.** `lemmatizer.lemmatize(word)` defaults
  to the noun part of speech and therefore never reduces verbs, so a
  lemmatiser silently underperforms a stemmer. Correct order: POS-tag
  the tokens, map the tags to the lemmatiser's tagset, then lemmatise.
- **Vocabulary size by stage** — `len(set(" ".join(df[col]).split()))`
  for raw, cleaned, stemmed, and lemmatised text. One number per stage
  shows how much each step compresses, and an ineffective step shows up
  as a flat line.

## 7. Vectorisation checks

- Bag of words with `CountVectorizer`, inspected on a **single document**
  as a word/count table sorted descending.
- TF-IDF over the same counts, inspected on the same document, then
  merged with the bag-of-words table on the shared word column. Seeing
  high-frequency and high-weight words diverge side by side is the point
  that the formula alone does not make.
- **Bigram frequency** (top-15 bar plot) tests the "bag of words loses
  order" claim with real numbers, and surfaces phrases worth keeping as
  features.

## 8. Sentiment and label cross-checks

- A lexicon scorer (VADER, TextBlob) gives a cheap cross-check against
  the human label: a polarity histogram by label, and a scatter of
  polarity against length hued by label.
- Inspect the mismatches. A document labelled negative scoring positive
  is either a mislabel or a construction the lexicon cannot read
  ("Not bad at all"), and both are findings.
- **Punctuation frequency by label** is a genuine signal, not noise:
  exclamation count, question count, capital ratio, and punctuation
  density are magnitude features distinct from polarity.
- **Word clouds** are qualitative only. Draw them per cleaning stage and
  split by label to eyeball class-associated vocabulary; never quote a
  cloud as a measurement.

## 9. Packaging and parity

- Bundle clean plus normalise behind one class with a single
  `tokenize()` entry point, so the vectoriser receives exactly the
  pipeline that was explored.
- **Pin the NLP library versions** `[external]`. Tokenisers and
  lemmatisers change behaviour between releases. Freeze the expected
  tokenisation of about 20 sample sentences as a regression test and run
  it on every upgrade.
- **Train and inference preprocessing must be the same function**
  `[external]`. Ship preprocessing inside the model package rather than
  as a notebook cell someone re-implements at serving time.
