# chimera

Claude Code plugin: skills, commands, agents, hooks, templates, and the
`rules/` pack. Chimera follows the rules it ships.

## Conventions
Coding rules (auto-loaded):
@rules/common/coding-style.md
@rules/common/documentation.md
@rules/python/coding-style.md

- Feature work and multi-file changes happen on branches - enter via
  /start-task, never directly on main.
- `plans/` is git-ignored working material; specs that ship live in
  `docs/specs/`.
- `docs/process-map.md` is the living process map. Any commit that
  alters a flow - a phase, a gate, a routing row, a skill's terminal
  state - updates the map in the same commit. A map that no longer
  matches the skills is treated the same as a stale requirement label.
