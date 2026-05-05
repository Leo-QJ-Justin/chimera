# chimera

Personal Claude Code plugin that composes existing plugins (Superpowers, planning-with-files) into an enterprise-ready feature development rhythm. Named for its hybrid nature — it doesn't reinvent any plugin, it wires them together with the missing connective tissue.

## Why it exists

Solo Claude Code workflows often skip discipline that matters in team settings: branch hygiene, spec-before-code, context persistence across sessions, dependency-aware backlog. The individual plugins handle pieces of this, but nothing wires them into a single forcing-function rhythm.

`chimera` ships:

- the **forcing-function hook** (branch enforcement) that no installed plugin provides, and
- the **orchestration command** that chains the right skills in the right order.

## v0.2 contents

- **`/start-feature`** — 8-step orchestration command. Pipeline: verify branch first (Step 0) → brainstorm spec → bootstrap `bd` epic → write plan → sync plan phases to `bd` issues with dependency edges → scaffold persistence layer → execute with `bd update --claim` / `bd close --reason` lifecycle → wrap up via `superpowers:finishing-a-development-branch`. Steps 0, 2, and 4 are new in v0.2.
- **`PreToolUse` hook on `Write|Edit|NotebookEdit`** — blocks edits when the current branch is `main` or `master`, with two carve-outs so chores and docs don't need a branch: (a) **path allowlist** — `*.md`, `docs/**`, and basenames `CHANGELOG*`/`README*`/`LICENSE*`/`.gitignore`/`.gitattributes`/`.editorconfig` auto-pass; (b) **escape hatch** — set `CHIMERA_ALLOW_MAIN=1` in the shell to skip the hook entirely (use for code-touching chores like dep bumps). No-ops in non-git directories.
- **`docs/testing/smoke.md`** — manual end-to-end smoke procedure (chimera is a markdown-instruction plugin; this replaces unit tests for v0.2).

## Dependencies (assumed installed separately)

**Plugin dependencies (Claude Code marketplace):**
- `superpowers@claude-plugins-official`
- `planning-with-files@planning-with-files`
- `pr-review-toolkit@claude-plugins-official` (used by `/start-feature` for review gate)
- `claude-mem@thedotmack` (optional — used for cross-session recall)

**System dependency:**
- `bd` v1.0.3+ from [gastownhall/beads](https://github.com/gastownhall/beads) — install with `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh | bash`. The `/start-feature` command preflights for `bd` and aborts with the install hint if it's missing.

## Install

```bash
# Add the marketplace
/plugin marketplace add Leo-QJ-Justin/chimera

# Enable the plugin
/plugin install chimera@chimera
```

## Status

v0.2 — beads integration into `/start-feature` (dependency-aware backlog tracking, claim/close lifecycle, cross-session recovery via `bd ready`). Built by dogfooding v0.1 to ship v0.2. Expect breaking changes through 0.x.

## Roadmap (v0.3+)

- **File-scoped branch hook** — current hook checks the CWD's branch, not the edited file's git context. Surfaced during chimera's own bootstrap when CWD inside chimera's repo on `main` blocked unrelated user-level config edits.
- ADR template scaffold (`templates/adr/`)
- Project-level `CLAUDE.md` template
- GitHub Actions CI skeleton template
- `pr-review-toolkit` wired in as a required `Stop` hook gate
- Wider branch-block patterns (`develop`, `release/*`, `staging`)
- Optional `Stop` hook warning if `bd ready` is non-empty but no `bd update --claim` happened this session

## License

MIT
