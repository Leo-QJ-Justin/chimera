# chimera v0.2 — Manual smoke test procedure

This procedure verifies that `/start-feature` produces all expected artifacts end-to-end. Run after every minor version bump (or whenever `commands/start-feature.md` changes meaningfully).

Estimated time: ~10–15 minutes.

## Prerequisites

- Claude Code running with chimera plugin loaded. Verify `chimera:start-feature` appears in the available skills listing.
- `bd` v1.0.3+ installed: `command -v bd && bd --version`.
- A throwaway working directory you can delete after.

## Procedure

### 1. Set up a throwaway repo

```bash
mkdir -p /tmp/chimera-smoke && cd /tmp/chimera-smoke
git init -q -b main
git -c user.email=test@test -c user.name=test commit --allow-empty -q -m init
git checkout -b feat/smoke-test
```

### 2. Trigger `/start-feature`

In Claude Code, with CWD = `/tmp/chimera-smoke`, invoke:

```
/start-feature
```

When the agent asks what feature to build, describe a trivial one:

> Add a `hello.txt` file containing the string `Hello, smoke test!`.

### 3. Walk through the 8-step pipeline

After each step, verify the expected artifact:

| Step | Expected artifact |
|---|---|
| 0. Verify branch | Agent confirms branch is `feat/smoke-test`, not `main`/`master`. |
| 1. Brainstorm | `docs/superpowers/specs/<date>-<topic>-design.md` created and committed. |
| 2. Bootstrap beads | `.beads/` directory exists; `bd list` shows one epic. |
| 3. Write plan | `docs/superpowers/plans/<date>-<feature>.md` created and committed. |
| 4. Sync plan → beads | `bd list --parent <epic-id>` shows one issue per phase; `bd show <phase-2-id>` shows dependency on phase 1. |
| 5. Scaffold persistence | `task_plan.md` exists at repo root, ≤30 lines, includes `EPIC_ID` and `PHASE_ID`s. |
| 6. Execute | Each phase: `bd ready` → claim → work → close. `bd show <phase-id>` shows full lifecycle in audit trail. |
| 7. Wrap up | Branch wrap-up invoked; epic remains `open`. |

### 4. Final verification (after wrap-up)

In a terminal (not Claude Code):

```bash
cd /tmp/chimera-smoke
echo '--- branch ---'; git rev-parse --abbrev-ref HEAD
echo '--- artifacts ---'; ls docs/superpowers/specs/ docs/superpowers/plans/
echo '--- bd state ---'; bd list --all
echo '--- task_plan.md ---'; head -30 task_plan.md
```

Expected:
- Branch is `feat/smoke-test` (or wrapped/merged depending on Step 7 choice).
- One spec file in `specs/`, one plan file in `plans/`.
- `bd list --all` shows: 1 epic with status `open`, N phases all `closed`.
- `task_plan.md` ≤30 lines with `EPIC_ID` and `PHASE_ID`s visible.

### 5. Cleanup

```bash
cd / && rm -rf /tmp/chimera-smoke
```

## Failure response

If any step fails to produce its expected artifact:

1. Note which step and what was missing in `docs/testing/smoke-failures.md` (create the file if needed).
2. File a new chimera issue (run from the chimera repo, e.g. `cd ~/dev/chimera`): `bd create "smoke failure: step N — <description>" --type bug`.
3. Investigate before shipping the version under test.
