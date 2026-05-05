# chimera

Personal Claude Code plugin that composes existing plugins (Superpowers, planning-with-files) into an enterprise-ready feature development rhythm. Named for its hybrid nature — it doesn't reinvent any plugin, it wires them together with the missing connective tissue.

## Why it exists

Solo Claude Code workflows often skip discipline that matters in team settings: branch hygiene, spec-before-code, context persistence across sessions, dependency-aware backlog. The individual plugins handle pieces of this, but nothing wires them into a single forcing-function rhythm.

`chimera` ships:

- the **forcing-function hook** (branch enforcement) that no installed plugin provides, and
- the **orchestration command** that chains the right skills in the right order.

## v0.1 contents

- **`/start-feature`** — orchestrates `superpowers:brainstorming` → `superpowers:writing-plans` → `planning-with-files:planning-with-files` → `superpowers:subagent-driven-development` → `superpowers:finishing-a-development-branch`.
- **`PreToolUse` hook on `Write|Edit|NotebookEdit`** — blocks edits when the current branch is `main` or `master`. No-ops in non-git directories. Bypass via the `/hooks` UI for legitimate edits to docs on main.

## Dependencies (assumed installed separately)

- `superpowers@claude-plugins-official`
- `planning-with-files@planning-with-files`
- `pr-review-toolkit@claude-plugins-official` (used by `/start-feature` for review gate)
- `claude-mem@thedotmack` (optional — used for cross-session recall)

## Install

```bash
# Add the marketplace
/plugin marketplace add Leo-QJ-Justin/chimera

# Enable the plugin
/plugin install chimera@chimera
```

## Status

v0.1 — bootstrapped from a single design session. Untested on real features yet. Will iterate as the rhythm gets exercised on real work; expect breaking changes through 0.x.

## Roadmap (v0.2+)

- ADR template scaffold (`templates/adr/`)
- BACKLOG / beads init helper
- Project-level `CLAUDE.md` template
- GitHub Actions CI skeleton template
- `pr-review-toolkit` wired in as a required `Stop` hook gate
- Wider branch-block patterns (`develop`, `release/*`, `staging`)

## License

MIT
