---
name: writing-plans
description: Use when a task has an approved spec or research brief and needs a written plan before implementation or experimentation begins
---

# Writing Plans

## Overview

Write for an implementer with no conversation context: exact files, code,
checks, small steps, and frequent commits. Use DRY, YAGNI, and TDD.

**Announce at start:** "I'm using the writing-plans skill to create the plan."

**Save plans to:** `plans/<task-slug>.md` — plan files are working state,
gitignored, never committed. (Specs and findings are committed; plans are
not.)

## Pattern Grounding (before writing any plan)

Capture one existing `file:line` example for each relevant convention:

- Build mode: naming, error handling, test structure
- Exploration mode: data loading, evaluation/metric computation

If none exists, say so; do not invent one.

## Mode Fork

**Build → implementation plan.** Each task follows RED → verify → GREEN →
verify → commit.

**Exploration → experiment plan:**
1. Data prep (snapshot to pin, with how it will be fingerprinted)
2. Baseline (the dumb thing to beat; from `docs/prd.md` if present)
3. Experiments, in order, each with: what varies, what's measured
4. Evaluation and guard metrics from the brief
5. **Stopping rule (mandatory):** "if <metric> improves less than <X> after
   <N> experiments, conclude no-signal and stop."

**A plan without a stopping rule is an incomplete exploration plan.**

## Plan Document Header

Every plan MUST start with:

```markdown
# [Task Name] Plan

> **Re-entry:** REQUIRED SUB-SKILL: chimera:test-driven-development (build)
> or chimera:exploring-reproducibly (exploration). Steps use checkbox
> (`- [ ]`) syntax; resume at the first unchecked step, trusting this file
> and git log over conversation memory.

**Mode:** build | exploration
**Spec:** docs/specs/<the approved spec/brief this implements>
**Goal:** [one sentence]

## Global Constraints

[Project-wide requirements from the spec, one line each, exact values
verbatim. Every task's requirements implicitly include this section.]

## Preconditions

[Every external resource a task step needs — a credential, an endpoint,
a dataset snapshot, a second process such as a conversion engine — with
the one command that proves it is live NOW. "none" is a valid entry.
/start-task Phase 4 runs these before Task 1.]

## Patterns to Mirror

[The Pattern Grounding citations: category → file:line → one-line note]

## Deviations

[Empty at approval. During execution, append every departure from the
spec or plan at the moment it is made: what changed, and the
implementer's rationale. A deviation that is not logged when made does
not exist at review time. finishing-a-branch passes this list to the
reviewer as questions.]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test_file.py`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks — exact signatures]
- Produces: [what later tasks rely on — exact names, parameter and return
  types, and the FORM of each value: the one spelling it takes, with the
  source rule where several places can supply it. A type is not a form,
  and the implementer sees only their own task; this block is how they
  learn what neighboring tasks expect.]

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run it — verify it fails for the right reason**

Run: `pytest tests/path/test_file.py::test_specific_behavior -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Minimal implementation**  (actual code block)
- [ ] **Step 4: Run tests — verify pass**
- [ ] **Step 5: Commit**  (exact git command with message)
````

Exploration tasks use the same shape with experiment steps: load pinned
snapshot → run baseline → record in findings doc → run experiment → record
→ check against stopping rule.

## Task Right-Sizing

A task carries one test cycle or experiment and can be reviewed alone.
Fold setup, config, and docs into its deliverable; split where a reviewer
could reject one task but approve its neighbor. Each step is one action.

**Bulk artifacts split at one unit.** Where a task produces many units of
one kind — fixtures, migrations, generated configuration, labelled data,
generated pages — the first unit is its own task: produce it, list every
judgment call it forced that the interface did not cover, and get a ruling
before the rest are produced. This meets the criterion above rather than
bending it: a reviewer genuinely could approve the first unit's rulings and
reject the batch built on them.

## No Placeholders

These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — tasks may be read out of order)
- Steps that describe without showing (code blocks required for code steps)
- References to types, functions, or metrics not defined in any task
- A form word with no rule beside it: "normalized", "canonical",
  "cleaned", "standard" — each names a decision nobody has made
- An experiment plan with no stopping rule

## Self-Review

After writing the complete plan, check against the spec with fresh eyes:

1. **Spec coverage:** every requirement maps to a task; list gaps.
2. **Placeholder scan:** search for the patterns above; fix them.
3. **Consistency:** names/signatures/metrics in later tasks match earlier
   definitions exactly.

Fix inline. No re-review.

## Handoff

Announce readiness; `/start-task` Phase 4 executes it in this session.
Subagents do not implement or commit.
