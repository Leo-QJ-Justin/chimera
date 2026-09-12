# Finishing a Branch — exception paths

> Sibling of `SKILL.md`. **Load when:** amending already-merged work,
> splitting work to a later roadmap row, folding a task's decisions into
> the living documents, or confirming a discard. The main skill covers
> the ordinary path; these are the ones that fire rarely and are
> improvised when they are not written down.

## If your human partner asks to discard the work

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
plan. Requirements: (a) tests move with the change; (b) every artifact
that encodes the amended behavior moves in the same commit — the living
documents (spec, PRD, system design, TRD), and also fixtures, labelled
data, tests, prompts and generated configuration; a requirement label
that no longer matches shipped behavior is stale, and so is a fixture.
Micro-branch optional; full test suite before the merge or commit, as
always.

## Split

When part of a task moves to a later roadmap row — a recording the
environment cannot make, a resource that is down — the unfinished work
goes on a named branch, **never a stash**: a stash is session-local and
conflicts with every edit made after it. The split is named in three
places: the inheriting roadmap row, the hand-off, and an execution
amendment to the current spec. Commit the carried work with a message
stating what makes it red and what would make it green.

The inheriting row re-validates those notes by trial rebase when it
starts (`/start-task` Phase 1) — a note written at the split describes
the tree at the split, and every merge since has moved it.

## Step 0b dispositions

A decision that changes an established convention — the form or source
of a value, an accepted rule — names every artifact that encodes the
previous answer: fixtures, labelled data, tests, prompts, generated
configuration. Each gets one of two dispositions:

- **moves in this branch** — the artifact is corrected here, in the
  same commit as the decision;
- **gets a roadmap row** — the correction is queued, and the row names
  the decision that obsoleted the artifact.

There is no third option. An artifact with no disposition is one that
silently holds a superseded answer, which is what this step exists to
prevent.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | yes | - | - | yes |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| Discard (explicit request only) | - | - | - | yes (force) |

