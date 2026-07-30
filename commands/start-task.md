---
description: Start one task through the chimera loop - design, plan, execute, verify, review, finish
argument-hint: "[task description | roadmap row reference | blank to pick from roadmap]"
---

# /start-task

**Input**: $ARGUMENTS

One trip through the loop. A **task** is any loop-sized unit of work: an app
feature, a data pipeline, an EDA pass, a model experiment, a refactor, a
spike. Announce each phase and create todos per phase.

**Resume rule:** if a `plans/<task-slug>.md` already exists for this task,
resume at its first unchecked step. Trust the plan file and `git log` over
conversation memory — do not re-do completed steps.

## Phase 0 — GATE

Run `git rev-parse --abbrev-ref HEAD` and `git status --porcelain`, then:

| State | Action |
|---|---|
| Already on a feature branch | Use it, continue |
| On main/master, clean tree | Create branch: `git checkout -b <type>/<slug>` (or offer a worktree: native tool preferred; else `.worktrees/<slug>` after `git check-ignore` confirms it's ignored) |
| On main/master, dirty tree | **STOP.** Ask: stash or commit the pending changes first |
| In a worktree | Use it, continue |

Never start task work on main/master without your human partner's explicit
consent. If not in a git repository, stop: "Run /new-project first."

## Phase 1 — MODE

If `$ARGUMENTS` references a `docs/roadmap.md` row, read the mode from the
row. Otherwise ask:

> "Is this producing code we'll keep (build), or an answer we'll act on
> (exploration)?"

The project CLAUDE.md `## Mode` line is the default; the answer here
overrides it. Record the mode — it goes at the top of the plan file and
shades every following phase.

## Phase 2 — DESIGN

Invoke chimera:designing-tasks. Output: committed spec (build) or research
brief (exploration) in `docs/specs/`. If the task came from the roadmap,
the spec references its row. Do not proceed without your human partner's
approval of the spec.

## Phase 3 — PLAN

Invoke chimera:writing-plans. Output: `plans/<task-slug>.md` (gitignored)
— implementation plan with per-task tests (build) or experiment plan with
stopping rule (exploration).

## Phase 4 — EXECUTE

Work the plan inline, one todo per plan task, following:
- Build → chimera:test-driven-development
- Exploration → chimera:exploring-reproducibly

**Circuit breaker:** the same error persisting after 3 fix attempts, or a
fix introducing more errors than it resolves → STOP and ask your human
partner (see chimera:debugging-systematically for the architecture
question).

**Early exit (exploration):** stopping rule reached → record the no-signal
result in the findings doc and jump to Phase 5.

## Phase 5 — VERIFY

Invoke chimera:verifying-before-done. Build: fresh full test run, read the
output. Exploration: clean rerun reproduces the findings numbers.

## Phase 6 — FINISH

Invoke chimera:finishing-a-branch (its Step 0 runs the one review pass).
After integration: if `docs/roadmap.md` exists, update this task's row
status and add any newly-created rows (e.g., a promotion task).
