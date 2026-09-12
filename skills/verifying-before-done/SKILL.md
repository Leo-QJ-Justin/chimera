---
name: verifying-before-done
description: Use before claiming work is complete, fixed, passing, or supported by analysis, and before committing, merging, or reporting results
---

# Verifying Before Done

## Overview

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist, from the realized `FR-N` *Done when* lines when a PRD exists | Tests passing |
| "The analysis shows X" | Clean rerun reproduces the numbers, and the instances behind any aggregate can be listed | Numbers remembered from an earlier run; an aggregate with no listing |

## Exploration Mode

A reported result is a completion claim. Before stating "the analysis shows
X" or recording a number in the findings doc as final:
- Rerun cleanly: restart the kernel / fresh process, run against the pinned
  snapshot with the recorded seed.
- The rerun's numbers must match the reported numbers. If they don't, the
  discrepancy IS the finding — investigate before reporting anything.

**An aggregate whose instances cannot be listed is not verified.** A rate,
a score or a failure count is a summary of instances, and only the
instances can be checked. If no output names the failing ones, the number
is unverified however many times it reproduces.

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- Tired and wanting work over
- Reporting a number from memory of an earlier run
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |
| "The notebook ran earlier" | Stale state lies; rerun clean |
| "Different words so rule doesn't apply" | Spirit over letter |

## Key Patterns

For regression tests, run with the fix, revert the fix and require failure,
then restore and require success. For requirements, use the realized FR
*Done when* lines when a PRD exists; otherwise use the plan.

## When To Apply

Apply before any statement implying success, satisfaction, correctness, or
completion; before commits, PRs, task transitions, and final numbers; and
after delegated work.
