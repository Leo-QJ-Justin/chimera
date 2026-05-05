# Changelog

All notable changes to chimera are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Changed
- Branch-enforcement hook now allows chores and docs on `main`/`master` without a branch. Two carve-outs: (1) path allowlist — `*.md`, `docs/**`, and basenames `CHANGELOG*`/`README*`/`LICENSE*`/`.gitignore`/`.gitattributes`/`.editorconfig` auto-pass; (2) escape hatch — `CHIMERA_ALLOW_MAIN=1` env var skips the hook for code-touching chores. Hook now uses `python3` (not `jq`) to parse the `tool_input` payload, since `jq` isn't a guaranteed dependency.
- `/start-feature` Step 0 unchanged — features still require a branch (the carve-outs are for the always-on hook only).

## [0.2.0] - 2026-05-05

### Added
- `/start-feature` integrates beads (`bd`) for dependency-aware backlog tracking. Each feature creates one beads epic and one issue per phase, with dependency edges between sequential phases. `bd ready --json` is used to surface the next claimable phase during execution.
- New `Step 0 — Verify branch` is now first in the pipeline (was Step 5 in v0.1), preventing the spec-write block we hit when starting on `main`/`master` during chimera's own bootstrap.
- `docs/testing/smoke.md` — manual end-to-end smoke procedure covering all 8 pipeline steps.

### Changed
- `commands/start-feature.md` rewritten from 7-step to 8-step pipeline. Steps 5 and 6 now reference bd IDs (in the `task_plan.md` dashboard) and use the `bd update --claim` / `bd close` lifecycle around each phase.

### Fixed (pre-release dogfood walkthrough)
- Step 6.3 close syntax — was `bd close <id> "<resolution>"` (wrong; beads errors trying to parse the resolution as another issue ID). Corrected to `bd close <id> --reason "<resolution>"`.
- Step 2.4 documented gotcha now covers both beads ID formats: flat (`bd-<prefix>-<hash>`) for top-level/epic issues, dotted (`<parent-id>.<int>`) for children. The `awk` extraction works for both; the previous warning implied only the flat form existed.

### Notes
- Requires `bd` v1.0.3+ from `gastownhall/beads`. Install: `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh | bash`.
- The branch hook is still CWD-scoped, not file-scoped. Tracked as a v0.3 candidate. Workaround documented in the workflow memory: `cd` to a non-git dir before editing user-level files.

## [0.1.0] - 2026-05-05

### Added
- `/start-feature` command — orchestrates Superpowers brainstorm/plan/execute with planning-with-files persistence and a branch-enforcement guard.
- `PreToolUse` hook on `Write|Edit|NotebookEdit` — blocks edits when current branch is `main` or `master`. No-ops in non-git directories.
- Plugin manifest, marketplace manifest, README, .gitignore, this changelog.

### Notes
- Bootstrapped from a single design session. Untested on real features yet — first iteration cycle is the next 3-5 features.
