---
description: Scaffold chimera project files - CLAUDE.md, gitignore, docs skeleton - into the current directory
argument-hint: "[blank]"
---

# /new-project

Thin scaffolding. Copies templates and initializes conventions — makes a
home for project docs without generating any.

## Phase 1 — PRECONDITIONS

- If `CLAUDE.md` already exists: show a diff of the proposed additions and
  **never overwrite without approval** — merge/append instead.
- If not a git repository: `git init -b main`.

## Phase 2 — GITIGNORE

Ensure `.gitignore` contains (append missing entries, preserve existing):

```
plans/
.worktrees/
```

plus stack defaults for the detected language (e.g. `__pycache__/`,
`.venv/`, `*.egg-info/` for Python; `node_modules/`, `dist/` for Node).

## Phase 3 — CLAUDE.md

Copy `${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE.project.md` and fill:

- **Brief**: ask for one paragraph — or take it from `docs/prd.md` if
  present (arriving from /design-project).
- **Default mode**: ask — build | exploration.
- **Commands**: probe `package.json` scripts, `pyproject.toml`, `Makefile`,
  `justfile`. **Only verified commands — never invent.** Leave "n/a" for
  anything not detected.
- **Architecture**: link `docs/prd.md`, `docs/system-design.md`,
  `docs/roadmap.md`, `docs/adr/` — only the ones that exist.

## Phase 3b — RULES

Copy the rules pack into the project — entire directories, never
flattened (`common/` and `python/` share filenames):

```bash
mkdir -p .claude/rules
cp -r "${CLAUDE_PLUGIN_ROOT}/rules" .claude/rules/chimera
```

If `.claude/rules/chimera/` already exists: show a diff of the differing
files and **never overwrite without approval**.

The filled CLAUDE.md imports what was copied. Keep the
`python/coding-style.md` import only for Python projects — the
`pyproject.toml` probe from Phase 3 decides; delete that line otherwise.

## Phase 4 — DOCS SKELETON

```bash
mkdir -p docs/specs docs/findings docs/adr
```

Add `notebooks/` for ML/hybrid projects (per the brief or PRD).

## Phase 5 — COMMIT

```bash
git add -A && git commit -m "chore: scaffold chimera project files"
```

Report what was created and what was skipped (already existed).

## Non-Goals

This command does NOT: generate PRDs or design docs (that's
/design-project), pick architecture, install dependencies, or create
application code.
