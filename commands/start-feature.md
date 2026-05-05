---
description: "Start a feature using the integrated Superpowers + planning-with-files workflow"
---

The user is starting a new feature. Follow this rhythm in order:

1. **Brainstorm the spec.** Invoke `superpowers:brainstorming`. Produce the design doc at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Get user approval before continuing.

2. **Write the implementation plan.** Invoke `superpowers:writing-plans`. Produce the bite-sized TDD plan at `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.

3. **Scaffold persistence files.** Invoke `planning-with-files:planning-with-files` to create `task_plan.md`, `findings.md`, `progress.md` at the repo root.

4. **Convert task_plan.md into a 25-line dashboard.** Replace the default phase scaffold with:
   - Goal (1 sentence)
   - Current Phase
   - Plan reference: pointer to `docs/superpowers/plans/<feature>.md`
   - Spec reference: pointer to `docs/superpowers/specs/<topic>-design.md`
   - Phases (mirror the Superpowers plan's task groups, with `**Status:** pending|in_progress|complete`)
   - Decisions Made table

   Must fit in <30 lines so the planning-with-files PreToolUse hook (`head -30 task_plan.md`) re-injects the whole thing on every Edit/Write/Bash.

5. **Verify branch.** Confirm not on main/master. The chimera branch-enforcement PreToolUse hook will block edits if so. If on main/master, create a feature branch (`git checkout -b feat/<name>` or invoke `superpowers:using-git-worktrees`).

6. **Execute.** Invoke `superpowers:subagent-driven-development` to run the plan task-by-task with TDD + two-stage review. While it runs, accumulate research in `findings.md` and session activity in `progress.md`.

7. **Wrap up.** When all phases complete, invoke `superpowers:finishing-a-development-branch`.

Use `claude-mem:mem-search` if you need to recall how a similar feature was handled in a prior session.

Add `task_plan.md` to git (committed for visibility); `findings.md`, `progress.md`, and `plans/` should be in `.gitignore`.
