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
