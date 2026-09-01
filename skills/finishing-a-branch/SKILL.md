---
name: finishing-a-branch
description: Use when a task's implementation or analysis is complete and verified, and you need to review and decide how to integrate the work
---

# Finishing a Branch

> Adapted from Superpowers `finishing-a-development-branch` (Jesse Vincent,
> MIT), with chimera's review gate folded in as Step 0.

## Overview

**Core principle:** Review → verify tests → detect environment → present
options → execute choice → clean up.

**Announce at start:** "I'm using the finishing-a-branch skill to complete this work."

## Step 0: Review Gate

One review pass, before anything merges. No Stop-hook re-review.

**Build mode:** dispatch the chimera `code-reviewer` agent once over
`BASE..HEAD`, passing: the range, the spec (`docs/specs/...`), the plan's
Global Constraints, the plan's `## Deviations` list — every known
deviation from the spec, each with the implementer's rationale, framed as
a question for the reviewer to judge, not a fact to accept — and
`mode: build`. Act by severity:
- Critical → fix now, before proceeding
- Important → fix before presenting the menu
- Minor → note; fix or record

**Exploration mode:** dispatch the same agent with `mode: exploration` and
the findings doc path — it runs the methodology rubric (leakage, look-ahead
bias, snapshot pinning, numbers-match-output, stopping rule honored,
decision line present).

**Handling feedback:** verify each finding against the code before
implementing; push back with evidence when the reviewer is wrong. Never
implement blindly; never respond with performative agreement — "You're
absolutely right!" is banned; state the fix or the counter-evidence.

## Step 1: Verify Tests

Run the project's full test suite. **Exploration mode:** the "suite" is the
clean rerun — findings numbers reproduce from the pinned snapshot.

**If tests fail**, report the failures and stop — the menu comes after a
green suite.

## Step 2: Detect Environment

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
# Capture now, while still inside the workspace - Step 5 changes directory
WORKTREE_PATH=$(git rev-parse --show-toplevel)
```

| State | Menu | Cleanup |
|-------|------|---------|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 3 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 3 options | Provenance-based (Step 6) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 2 options (no merge) | Externally managed — leave in place |

## Step 3: Determine Base Branch

The base is whatever this work forked from. If not already known, ask:
"This branch split from <best guess> - is that correct?" Confirm before
merging — merging into the wrong base is expensive to undo.

## Step 4: Present Options

**Build mode — present exactly these 3 options:**

```
Task complete and reviewed. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)

Which option?
```

**Exploration mode — present exactly these 3 options:**

```
Analysis complete and reviewed. Findings and decision are recorded in
docs/findings/<file>. What would you like to do?

1. Merge the findings doc to <base-branch>; archive the experiment code on
   this branch (not merged - see the promotion rule)
2. Push and create a Pull Request (findings + notebooks for reference)
3. Keep the branch as-is (I'll handle it later)

Which option?
```

**Detached HEAD — present exactly these 2 options:**

```
Task complete. You're on a detached HEAD (externally managed workspace).

1. Push as new branch and create a Pull Request
2. Keep as-is (I'll handle it later)

Which option?
```

Present the menu exactly as written. Discarding work happens ONLY in
response to your human partner explicitly asking for it (below). Wait for
their answer; the integration decision is theirs.

## Step 5: Execute Choice

### Option 1: Merge Locally

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
git checkout <base-branch>
git pull
git merge <feature-branch>
<test command>   # verify the MERGED result
```

If tests fail on the merged result: stop, leave everything in place,
investigate — nothing is pushed, the merge is recoverable.

Once green: clean up worktree (Step 6), then `git branch -d <branch>`.
**Exploration:** if a promotion was decided, add the promotion task to
`docs/roadmap.md` before deleting the branch. Update the roadmap row status.

### Option 2: Push and Create PR

```bash
git push -u origin <feature-branch>
```

Create the PR against <base-branch>: conventional-commit title from the
dominant commit type; follow the repo's PR template if present; **no
boilerplate footers, no generated-with lines, no co-author lines**. Report
the URL. Keep the worktree — PR feedback gets fixed there. A rejected push
means the remote moved: investigate; force-push only on your human
partner's explicit request (and then `--force-with-lease`, never
`--force`).

### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

### If your human partner asks to discard the work

Only as a response to an explicit request. Confirm first:

```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for that exact word. Then cd to MAIN_ROOT, clean up (Step 6), and
`git branch -D <branch>`.

## Amendment path

For post-merge scope corrections: a small behavior change to
already-integrated work, requested after the loop closed. No spec, no
plan. Requirements: (a) tests move with the change; (b) every document
that states the amended behavior — spec, PRD, system design — moves in
the same commit; a requirement label that no longer matches shipped
behavior is stale. Micro-branch optional; full test suite before the
merge or commit, as always.

## Step 6: Cleanup Workspace

Runs for Option 1 and confirmed discards; Options 2 and 3 always preserve
the worktree. Uses the Step 2 values captured before any cd.

- `GIT_DIR == GIT_COMMON`: normal repo, nothing to clean. Done.
- `WORKTREE_PATH` under `.worktrees/` or `worktrees/`: chimera created it —
  `git worktree remove "$WORKTREE_PATH" && git worktree prune`
- Otherwise: the host environment owns the workspace — leave it in place.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | yes | - | - | yes |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| Discard (explicit request only) | - | - | - | yes (force) |

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Tests passed earlier this session" | Run the suite on the tree you are about to integrate. A green run only proves the tree it ran on. |
| "The diff is small, skip the review" | Small diffs hide load-bearing bugs. One review pass, every task. |
| "The reviewer's finding is annoying, just do it" | Verify it first. Wrong findings get evidence-based pushback, not blind compliance. |
| "They obviously want it merged" | Integration is your human partner's decision. Present the menu and wait. |
| "'Yeah, get rid of it' counts as confirmation" | Only the typed word `discard` authorizes deletion. |
| "The PR is up, so the worktree is clutter now" | PR feedback gets fixed in that worktree. It stays until the work lands. |
| "This other worktree looks stale - I'll clean it too" | Clean only worktrees under `.worktrees/` or `worktrees/`. Everything else belongs to the host. |
| "The merged-result failure is probably flaky" | A failing merged result stops everything. Branch and worktree stay put while you investigate. |
| "The base branch is obviously main" | Confirm the fork point or ask. Wrong-base merges are expensive to undo. |
| "The notebook should ship with the pipeline" | Experiment code is archived, not merged as production. Promotion is a new build-mode task. |
