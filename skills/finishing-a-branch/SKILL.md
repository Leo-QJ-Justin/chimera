---
name: finishing-a-branch
description: Use when a task's implementation or analysis is complete and verified, and you need to review and decide how to integrate the work
---

# Finishing a Branch

## Overview

Review → fold decisions → verify → detect environment → present options →
execute choice → clean up.

**Announce at start:** "I'm using the finishing-a-branch skill to complete this work."

Exception paths (detached HEAD, Amendment, Split, discard, dispositions):
[post-loop-paths.md](post-loop-paths.md).

## Step 0: Review Gate

One review pass, before anything merges. No Stop-hook re-review.

**Build:** dispatch `code-reviewer` once over `BASE..HEAD`. Pass the range,
spec, Global Constraints, and every `## Deviations` item with its rationale
as a question, plus `mode: build`. Act by severity:
- Critical → fix now, before proceeding
- Important → fix before presenting the menu
- Minor → note; fix or record

**Exploration:** pass `mode: exploration` and the findings path for the
methodology rubric: leakage, look-ahead bias, snapshot, reproduced numbers,
stopping rule, and decision line.

Verify findings before acting. State the fix or counter-evidence; no blind
implementation or performative agreement.

## Step 0b: Fold Decisions Into the Living Documents

After review fixes, walk the spec's Decisions before the suite so it covers
the tree that merges.

Mark each entry **task-local**, or rewrite the current statement and reason
in its living document (system design, TRD, data model, CLAUDE.md, prompt
contract). Living documents carry no amendment chains. A convention change
also gives every artifact holding the old answer a disposition
([post-loop-paths.md](post-loop-paths.md)). Present no menu until each
decision has a home.

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
| `GIT_DIR != GIT_COMMON`, detached HEAD | Load sibling; reduced menu | Externally managed — leave in place |

## Step 3: Determine Base Branch

Confirm the fork point before merging. If unknown, ask: "This branch split
from <best guess> - is that correct?"

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

Present the menu exactly as written. Discarding work happens ONLY in
response to your human partner explicitly asking for it. Wait for their
answer; the integration decision is theirs.

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

Create the PR against <base-branch> with a conventional title and the repo
template. Add no generated or co-author footer. Report the URL and keep the
worktree for feedback. On rejection, investigate; force-push only by
explicit request, with `--force-with-lease`.

### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

### If your human partner asks to discard the work

Only on an explicit request; wording and the required word are in the
sibling file.

## Step 6: Cleanup Workspace

Run for Option 1 and confirmed discards. Options 2 and 3 preserve the
worktree. Use the Step 2 values captured before `cd`.

- `GIT_DIR == GIT_COMMON`: normal repo, nothing to clean. Done.
- `WORKTREE_PATH` under `.worktrees/` or `worktrees/`: chimera created it —
  `git worktree remove "$WORKTREE_PATH" && git worktree prune`
- Otherwise: the host environment owns the workspace — leave it in place.

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
| "Every decision here is task-local" | Then Step 0b costs 30 seconds. Say it per entry; a blanket answer is the one that leaves fixtures holding a superseded convention. |
