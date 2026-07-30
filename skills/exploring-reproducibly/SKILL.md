---
name: exploring-reproducibly
description: Use when starting exploration-mode work - EDA, model experiments, backtests, hypothesis tests, technical spikes - before opening a notebook or running any analysis
---

# Exploring Reproducibly

Chimera's exploration-mode discipline. The build-mode counterpart is
chimera:test-driven-development.

## Overview

**Core principle:** A result that cannot be re-run is not a result. The
deliverable of exploration is a recorded decision, not code.

**Violating the letter of this process is violating its spirit.**

## The Iron Law

```
NO ANALYSIS WITHOUT A BRIEF, NO RESULT WITHOUT A RERUN
```

Tripwire: opening a notebook without a research brief → stop, write the
brief (chimera:designing-tasks). The brief names the question, the method,
and *what result would change what decision*. Analysis without that line is
wandering, not exploring.

## Pin Everything

Before the first computation:

- **Data snapshot** — an immutable path or query, recorded with a hash or
  row-count fingerprint in the findings doc header. "The latest data" is
  not a snapshot.
- **Random seeds** — set and recorded wherever stochasticity exists
  (sampling, splits, model init).
- **Environment** — note the interpreter/env name; pin versions if a result
  will feed a decision.

## Log As You Go

Findings live in `docs/findings/YYYY-MM-DD-<topic>.md` (committed). Each
entry, written **at observation time**:

```
### <assumption or question>
- Experiment: <what was run, which notebook/script>
- Result: <the number(s), verbatim from output>
- Interpretation: <what it means for the question>
```

Reconstructed findings are fiction with confidence. If it isn't logged when
observed, it didn't happen.

## Honor the Stopping Rule

The experiment plan (chimera:writing-plans) defines a stopping rule —
"if <metric> improves less than <X> after <N> experiments, conclude
no-signal and stop." Extending the search requires editing the plan first,
with the reason recorded. This is the guard against endless fishing.

## Notebook Conventions

- Notebooks live in `notebooks/`, named `NN-topic.ipynb` (ordered).
- Structure: objective cell (from the brief) → data loading (pinned
  snapshot stated) → analysis → findings-summary cell mirroring the
  findings-doc entry.
- Project-specific data locations belong in the project CLAUDE.md, not
  hardcoded surprises mid-notebook.

## Ending a Task

The findings doc closes with a decision line:

```
Decision: <adopt | reject | park> because <numbers>
```

Exits:
- **Adopt** → promoting the result is a NEW build-mode task; the experiment
  code is reference only (chimera:test-driven-development, The Promotion
  Rule).
- **Reject / park** → the recorded decision is the deliverable; archive the
  notebook.

Before recording any final number: clean rerun on the pinned snapshot must
reproduce it (chimera:verifying-before-done, Exploration Mode).

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "It's just a quick look" | Quick looks that inform decisions are experiments. Brief first — it can be three sentences. |
| "I'll write up findings at the end" | End-of-session write-ups reconstruct; observation-time logs record. Log as you go. |
| "The seed doesn't matter here" | Then setting it costs one line. Unset seeds are why the rerun won't match. |
| "This run is close enough to the reported one" | "Close" means not reproduced. Investigate the gap or re-report the actual number. |
| "One more feature combination might do it" | Check the stopping rule. If you're past it, the answer is no-signal — record it. |
| "The notebook works, just productionize it" | That's a copy-paste promotion. The promotion rule exists because notebook code silently becomes untested pipelines. |

## Red Flags - STOP

- Running analysis with no brief in `docs/specs/`
- A findings doc with numbers but no pinned snapshot named
- "Latest data" anywhere in a result
- Reporting from memory of an earlier run
- Experiment count past the stopping rule with no plan edit
- Merging notebook code into pipeline directories
