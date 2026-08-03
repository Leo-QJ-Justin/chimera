# Chimera rules

Explicit coding rules in ECC's format: short, imperative files that state
WHAT to do. Skills state HOW.

## Layout

- `common/` - language-agnostic, loaded for every project.
- `python/` - Python specifics, `paths:` frontmatter, extends `common/`.

Specific overrides general: where `python/coding-style.md` and
`common/coding-style.md` speak to the same point, the Python file wins.

## Install

Rules travel by copy, not by plugin load, so every tool that reads the
repo sees them. `/new-project` copies them during scaffolding. For an
existing project:

```bash
mkdir -p .claude/rules
cp -r "${CLAUDE_PLUGIN_ROOT}/rules" .claude/rules/chimera
```

Copy entire directories. Never flatten: `common/` and `python/` both hold
a `coding-style.md`, and a flattened copy clobbers one with the other.

In Claude Code the copies auto-load through `@` imports in the project
CLAUDE.md. Updating the plugin does not update a project's copy - re-copy
or diff `.claude/rules/chimera/` deliberately.
