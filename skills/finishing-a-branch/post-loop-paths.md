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
plan. Requirements: (a) tests move with the change; (b) every document
that states the amended behavior — spec, PRD, system design — moves in
the same commit; a requirement label that no longer matches shipped
behavior is stale. Micro-branch optional; full test suite before the
merge or commit, as always.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | yes | - | - | yes |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| Discard (explicit request only) | - | - | - | yes (force) |

