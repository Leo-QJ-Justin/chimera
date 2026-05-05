---
description: "Start a feature using the integrated Superpowers + planning-with-files + beads workflow"
---

The user is starting a new feature. Follow this 8-step rhythm in order. Steps 0, 2, and 4 are new in v0.2; the others are unchanged or renumbered from v0.1.

### Step 0 — Verify branch (FIRST, before anything else)

Run `git rev-parse --abbrev-ref HEAD`. If the result is `main` or `master`, refuse and instruct the user to create a feature branch (`git checkout -b feat/<name>`) or invoke `superpowers:using-git-worktrees`. Halt the rhythm.

If on a feature branch, proceed.

### Step 1 — Brainstorm the spec

Invoke `superpowers:brainstorming`. Produce the design doc at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Get user approval before continuing.

### Step 2 — Bootstrap beads

1. **Preflight:** `command -v bd >/dev/null`. If `bd` is missing, print this install hint to stderr and abort the rhythm:

   ```
   Install beads first:
     curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh | bash
   ```

2. **Init if absent:** if `.beads/` does not exist in the repo, run `bd init` silently. The `.beads/` directory will be committed alongside the first epic.

3. **Create the epic:**

   ```
   bd create "<feature title>" --type epic -p 0 \
     -d "Spec: docs/superpowers/specs/<topic>-design.md"
   ```

4. **Capture `EPIC_ID`** from `bd create` output. First try `bd create ... --json` (parse `.id`). If `--json` is unsupported, fall back to:

   ```
   awk '/Created issue:/ {print $4; exit}'
   ```

   on stdout. **Important — beads issue IDs have two formats:** epics and top-level issues use `bd-<lowercase-prefix>-<hash>` (multiple dashes, e.g. `bd-chimera-7nq`); children created with `--parent` use `<parent-id>.<integer>` (e.g. `bd-chimera-7nq.1`). The `awk '/Created issue:/ {print $4; exit}'` approach works for both because it's whitespace-delimited. Do NOT use a greedy regex like `bd-[a-z0-9]+` — it silently matches only `bd-<prefix>` for top-level IDs and breaks completely on children.

### Step 3 — Write the implementation plan

Invoke `superpowers:writing-plans`. Produce the bite-sized TDD plan at `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.

### Step 4 — Sync plan → beads

For each phase in the Superpowers plan, in plan order:

1. Create the phase issue:

   ```
   bd create "<phase title>" --parent $EPIC_ID -p 1 \
     -d "Files: <file paths from the Superpowers plan task's Files: section>
         Acceptance: <one-to-two sentence summary of what 'done' looks like>"
   ```

   Default priority is **P1** (high) for all phases. P0 is reserved for emergency/blocker phases.

2. Capture each `PHASE_ID` using the same `--json` / `awk` extraction approach described in Step 2.4.

For sequential phases (Phase N depends on Phase N-1):

3. `bd dep add <PHASE_ID_n> <PHASE_ID_n-1>` — encodes ordering as dependency edges so `bd ready` surfaces them in the right sequence.

Then:

4. **Hold `EPIC_ID` and the ordered list of `PHASE_ID`s in working memory.** Step 5 will write them into `task_plan.md` when it scaffolds the dashboard.

### Step 5 — Scaffold persistence files

Invoke `planning-with-files:planning-with-files` to scaffold `task_plan.md`, `findings.md`, `progress.md` at the repo root. Then convert `task_plan.md` to the chimera dashboard format, **populating it with the `EPIC_ID` and `PHASE_ID`s captured in Step 4**:

```markdown
# Task Plan: <feature title>

## Goal
<one-sentence statement of what we're building>

## Current Phase
Phase 1 [<PHASE_ID_1>] — <phase-1-title>

## Plan reference
docs/superpowers/plans/YYYY-MM-DD-<feature>.md

## Spec reference
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md

## Beads epic
<EPIC_ID>

## Phases
### Phase 1 [<PHASE_ID_1>] — <phase-1-title>
- **Status:** in_progress
### Phase 2 [<PHASE_ID_2>] — <phase-2-title>
- **Status:** pending

## Decisions Made
| Decision | Rationale |
|---|---|
```

Must fit in <30 lines so the planning-with-files PreToolUse hook (`head -30 task_plan.md`) re-injects the whole dashboard on every Edit/Write/Bash.

Add `task_plan.md` to git (committed for visibility); `findings.md`, `progress.md`, and `plans/` should be in `.gitignore`.

### Step 6 — Execute

For each phase, in the order surfaced by `bd ready --json`:

1. `bd update <phase-id> --claim` (atomic; prevents duplicate claims by parallel sessions).
2. Run TDD steps from the Superpowers plan for this phase. Use `superpowers:subagent-driven-development`.
3. `bd close <phase-id> --reason "<resolution>"` once tests green and committed. The `--reason` flag is required — `bd close <id> "text"` (without `--reason`) makes beads try to interpret the resolution as another issue ID and errors.
4. Update `task_plan.md` dashboard's Phase status to `complete`.

### Step 7 — Wrap up

Invoke `superpowers:finishing-a-development-branch`. The epic remains `open` after wrap-up so the user can add follow-up tasks; user closes it explicitly when done.

Use `claude-mem:mem-search` if you need to recall how a similar feature was handled in a prior session.
