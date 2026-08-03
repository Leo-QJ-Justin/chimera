# {{PROJECT_NAME}}

{{ONE_PARAGRAPH_BRIEF}}

## Mode
Default: {{build | exploration}}  (tasks may override at /start-task)

## Commands
- build: {{cmd or "n/a"}}
- test: {{cmd or "n/a"}}
- lint: {{cmd or "n/a"}}
- run: {{cmd or "n/a"}}

## Architecture
{{5-10 line map. Link, don't inline: [PRD](docs/prd.md) ·
[system design](docs/system-design.md) · [roadmap](docs/roadmap.md) ·
[ADRs](docs/adr/)}}

## Conventions
Coding rules (auto-loaded):
@.claude/rules/chimera/common/coding-style.md
@.claude/rules/chimera/common/documentation.md
@.claude/rules/chimera/python/coding-style.md {{delete if not a Python project}}

- Feature work and multi-file changes happen on branches - enter via
  /start-task, never directly on main.
{{3-5 more that differ from defaults; delete if none}}

## Gotchas
{{known traps: env quirks, data locations, slow tests; delete if none}}
