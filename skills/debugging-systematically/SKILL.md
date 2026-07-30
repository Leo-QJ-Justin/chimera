---
name: debugging-systematically
description: Use when encountering any bug, test failure, or unexpected behavior - including a pipeline producing wrong numbers or an experiment result that makes no sense - before proposing fixes
---

# Debugging Systematically

> Adapted from Superpowers `systematic-debugging` (Jesse Vincent, MIT).

## Overview

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue: test failures, bugs, unexpected behavior,
performance problems, build failures, integration issues — and in
exploration mode, a result that makes no sense (impossibly good metric,
numbers that changed between runs).

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- It's "just an analysis notebook" (wrong numbers become wrong decisions)

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings — they often contain the exact solution
   - Read stack traces completely; note line numbers, file paths, error codes

2. **Reproduce Consistently**
   - Can you trigger it reliably? What are the exact steps?
   - If not reproducible → gather more data, don't guess
   - **Exploration mode:** before suspecting the code, check the pinned
     snapshot and seed — an unpinned input or unset seed is the most common
     "impossible result" root cause

3. **Check Recent Changes**
   - What changed that could cause this? Git diff, recent commits
   - New dependencies, config changes, environmental differences

4. **Gather Evidence in Multi-Component Systems**

   WHEN the system has multiple components (ingest → transform → model →
   report; API → service → database), add diagnostic instrumentation BEFORE
   proposing fixes:

   ```
   For EACH component boundary:
     - Log what data enters the component
     - Log what data exits the component
     - Verify environment/config propagation
     - Check state at each layer

   Run ONCE to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify the failing component
   THEN investigate that specific component
   ```

   For a pipeline: log row counts, schema, and a checksum at each stage —
   the stage where they diverge from expectation is where you investigate.

5. **Trace Data Flow**
   - Where does the bad value originate? What called this with the bad value?
   - Keep tracing up until you find the source. Fix at source, not at symptom.

### Phase 2: Pattern Analysis

1. **Find Working Examples** — similar working code in the same codebase
2. **Compare Against References** — read reference implementations
   COMPLETELY; don't skim
3. **Identify Differences** — list every difference, however small; don't
   assume "that can't matter"
4. **Understand Dependencies** — settings, config, environment, assumptions

### Phase 3: Hypothesis and Testing

1. **Form Single Hypothesis** — "I think X is the root cause because Y."
   Write it down. Be specific.
2. **Test Minimally** — smallest possible change, one variable at a time
3. **Verify Before Continuing** — worked? → Phase 4. Didn't? → NEW
   hypothesis. DON'T add more fixes on top.
4. **When You Don't Know** — say "I don't understand X." Don't pretend.
   Ask for help. Research more.

### Phase 4: Implementation

1. **Create Failing Test Case** — simplest reproduction, automated if
   possible. MUST have before fixing. Use chimera:test-driven-development.
2. **Implement Single Fix** — the root cause, ONE change, no "while I'm
   here" improvements, no bundled refactoring.
3. **Verify Fix** — test passes, nothing else broken, issue actually
   resolved. Use chimera:verifying-before-done before claiming success.
4. **If Fix Doesn't Work** — STOP. Count your fix attempts.
   - If < 3: return to Phase 1 and re-analyze with the new information
   - **If ≥ 3: STOP and question the architecture (below)**
   - DON'T attempt Fix #4 without architectural discussion
5. **If 3+ Fixes Failed: Question Architecture**
   - Pattern: each fix reveals new coupling/problem elsewhere; fixes need
     "massive refactoring"; each fix creates new symptoms
   - STOP and ask: is this pattern fundamentally sound, or held by inertia?
   - Discuss with your human partner before attempting more fixes.
   - This is NOT a failed hypothesis — this is a wrong architecture.

## Red Flags - STOP and Follow Process

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**

**ALL of these mean: STOP. Return to Phase 1.**

## Your Human Partner's Signals You're Doing It Wrong

- "Is that not happening?" — you assumed without verifying
- "Will it show us...?" — you should have added evidence gathering
- "Stop guessing" — you're proposing fixes without understanding
- "We're stuck?" (frustrated) — your approach isn't working

**When you see these:** STOP. Return to Phase 1.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write the test after confirming the fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |

## When Process Reveals "No Root Cause"

If systematic investigation reveals the issue is truly environmental,
timing-dependent, or external: document what you investigated, implement
appropriate handling (retry, timeout, error message), add logging for
future investigation.

**But:** 95% of "no root cause" cases are incomplete investigation.
