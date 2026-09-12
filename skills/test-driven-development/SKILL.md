---
name: test-driven-development
description: Use when implementing any build-mode task - any feature, bugfix, pipeline, or production code - before writing implementation code
---

# Test-Driven Development (TDD)

## Overview

Write the test first, watch it fail, then write minimal code to pass. A test
not seen failing has not proved that it tests the intended behavior.

**Violating the letter of the rules is violating the spirit of the rules.**

## When to Use

Use for all build-mode features, fixes, refactors, behavior changes, data
pipelines, feature engineering, and IO adapters.

Exploration work uses chimera:exploring-reproducibly.

Ask your human partner before exempting throwaway prototypes, generated
code, or configuration. Thinking "skip TDD once" is rationalization.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

Do not keep, inspect, or adapt it as reference. Implement fresh from tests.

## Scope: The Deterministic Boundary (ML/data projects)

In build mode, TDD covers everything deterministic: data transforms, schema
and shape contracts, joins, feature computations, leakage checks, IO
adapters. Model *quality* is not a unit test - accuracy/MAE/lift targets are
evaluation metrics, owned by exploration-mode findings against the pinned
snapshot. Do not fake a quality bar as an assertion; do not use "ML is
stochastic" to skip testing the deterministic 90% of the pipeline.

## The Promotion Rule

When an exploration result wins and must live on, promoting it is a NEW
build-mode task. The experiment/spike code is reference material, never the
implementation. Write the pipeline version test-first; the experiment's
numbers on the pinned data snapshot are the acceptance criteria (the
pipeline must reproduce them). Spike code is not merged.

## Red-Green-Refactor

RED (write failing test) → Verify RED (watch it fail, for the right reason)
→ GREEN (minimal code) → Verify GREEN (all tests pass, output pristine) →
REFACTOR (stay green) → repeat.

### RED - Write Failing Test

Write one clearly named test for one observable behavior, using real code
unless a dependency is slow or external.

### Verify RED - Watch It Fail

**MANDATORY. Never skip.**

```bash
pytest tests/path/test_module.py::test_name -v
```

Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

**Test passes?** You're testing existing behavior. Fix test.

**Test errors?** Fix error, re-run until it fails correctly.

### GREEN - Minimal Code

Write the simplest code to pass the test. Don't add features, refactor
other code, or "improve" beyond the test. YAGNI.

### Verify GREEN - Watch It Pass

**MANDATORY.**

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix code, not test.

**Other tests fail?** Fix now.

### REFACTOR - Clean Up

After green only: remove duplication, improve names, extract helpers.
Keep tests green. Don't add behavior.

## Good Tests

Before each test body:

1. Name the production change that would make the test fail.
2. Derive expected values independently of production helpers.
3. Assert real behavior, not mock existence.

Load [writing-good-tests.md](writing-good-tests.md) only when using mocks or
fakes, adding test helpers or cleanup, testing source/config/documents, or
deriving expected values through nontrivial helpers.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | A test that passes immediately proves nothing. You never saw it catch the missing behavior. |
| "Tests after achieve same goals (spirit not ritual)" | Tests-after describe existing code; tests-first define required behavior without implementation bias. |
| "Already manually tested" | Manual checks leave no repeatable record and miss cases under pressure. |
| "Deleting X hours is wasteful" | The time is spent. Keeping unproven code adds more cost. |
| "Keep as reference, write tests first" | You'll adapt it. That's testing after. Delete means delete. |
| "Need to explore first" | Fine — that's an exploration-mode spike. Throw the spike away, then build with TDD (see The Promotion Rule). |
| "Test hard = design unclear" | Listen to test. Hard to test = hard to use. |
| "TDD will slow me down" | It catches bugs before commit and makes refactoring safe. |
| "It's ML code, it's stochastic" | The pipeline around the model is deterministic. Test it. Fix seeds where determinism is by choice. |
| "Existing code has no tests" | You're improving it. Add tests for existing code. |

## Red Flags - STOP and Start Over

- Code before test
- Test after implementation
- Test passes immediately
- Can't explain why test failed
- Tests added "later"
- Rationalizing "just this once"
- "I already manually tested it"
- "Tests after achieve the same purpose"
- "It's about spirit not ritual"
- "Keep as reference" or "adapt existing code"
- "Already spent X hours, deleting is wasteful"
- "TDD is dogmatic, I'm being pragmatic"
- Copy-pasting notebook code into a pipeline "because it already works"
- "This is different because..."

**All of these mean: Delete code. Start over with TDD.**

## Verification Checklist

Before marking work complete:

- [ ] Each new behavior has a test that failed for the expected reason.
- [ ] Minimal code made it pass; refactoring stayed green.
- [ ] The full suite passes with no errors or warnings.
- [ ] Tests exercise real behavior and cover errors and boundaries.

Can't check all boxes? You skipped TDD. Start over.

## When Stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write wished-for API. Write assertion first. Ask your human partner. |
| Test too complicated | Design too complicated. Simplify interface. |
| Must mock everything | Code too coupled. Use dependency injection. |
| Test setup huge | Extract helpers. Still complex? Simplify design. |

## Debugging Integration

Bug found? Write failing test reproducing it (chimera:debugging-systematically
Phase 4). Follow TDD cycle. Test proves fix and prevents regression.

Never fix bugs without a test.

## Final Rule

```
Production code → test exists and failed first
Otherwise → not TDD
```

No exceptions without your human partner's permission.
