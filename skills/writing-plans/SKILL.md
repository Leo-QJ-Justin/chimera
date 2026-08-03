---
name: writing-plans
description: Use when a task has an approved spec or research brief and needs a written plan before implementation or experimentation begins
---

# Writing Plans

> Adapted from Superpowers `writing-plans` (Jesse Vincent, MIT) with ECC's
> Pattern Grounding and chimera's experiment-plan variant.

## Overview

Write plans assuming the implementer has zero context for this codebase and
questionable taste. Document everything they need: which files to touch,
the code itself, how to test it, bite-sized steps. DRY. YAGNI. TDD.
Frequent commits.

**Announce at start:** "I'm using the writing-plans skill to create the plan."

**Save plans to:** `plans/<task-slug>.md` — plan files are working state,
gitignored, never committed. (Specs and findings are committed; plans are
not.)

## Pattern Grounding (before writing any plan)

Search the codebase for the conventions this plan must mirror. Capture ONE
existing example per relevant category, cited as `file:line`:

- Build mode: naming, error handling, test structure
- Exploration mode: data loading, evaluation/metric computation

**If no similar code exists, state that explicitly in the plan. Do not
invent a pattern.**

## Mode Fork

**Build mode → implementation plan.** Every task carries its own test
cycle; steps follow RED → verify → GREEN → verify → commit
(chimera:test-driven-development).

**Exploration mode → experiment plan.** Structure:
1. Data prep (snapshot to pin, with how it will be fingerprinted)
2. Baseline (the dumb thing to beat; from `docs/prd.md` if present)
3. Experiments, in order, each with: what varies, what's measured
4. Evaluation metric, plus the guard metric it must not be bought at the
   expense of (both inherited from the brief, which takes them from the
   PRD when it exists)
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

## Patterns to Mirror

[The Pattern Grounding citations: category → file:line → one-line note]

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
  types. The implementer sees only their own task; this block is how they
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

A task is the smallest unit that carries its own test cycle (or experiment)
and is worth a fresh reviewer's gate. Fold setup, config, and docs into the
task whose deliverable needs them; split only where a reviewer could reject
one task while approving its neighbor. Each step is one action (2-5 min).

## No Placeholders

These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — tasks may be read out of order)
- Steps that describe without showing (code blocks required for code steps)
- References to types, functions, or metrics not defined in any task
- An experiment plan with no stopping rule

## Self-Review

After writing the complete plan, check against the spec with fresh eyes:

1. **Spec coverage:** every requirement maps to a task; list gaps.
2. **Placeholder scan:** search for the patterns above; fix them.
3. **Consistency:** names/signatures/metrics in later tasks match earlier
   definitions exactly.

Fix inline. No re-review.

## Handoff

The plan is executed by `/start-task` Phase 4 in this session — announce
readiness and proceed. Do not dispatch subagents to implement (subagents
never commit).
