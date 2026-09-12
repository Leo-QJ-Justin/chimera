---
name: creating-skills
description: Use when creating a new skill or editing an existing one - for chimera, a project, or global use - before writing or changing any SKILL.md content
---

# Creating Skills

## Overview

**Core principle:** a skill is behavior-shaping code. It earns its context
cost or does not ship.

Create a todo per step below; complete them in order.

## Step 1: The Gate — should this be a skill at all?

Answer before writing anything:

1. **Overlap scan.** Grep existing skills — this project's `.claude/skills/`,
  chimera's `skills/`, and `~/.claude/skills/`. Prefer absorption.
2. **Mechanical constraint?** If a regex, linter, formatter, or hook can
   enforce it, automate it. Documentation is for judgment calls only.
3. **Repeated situation?** One-off knowledge belongs in findings docs or
   the project CLAUDE.md, not a skill.
4. **Placement.** Project-specific → project `.claude/skills/`; universal →
  global or chimera; uncertain → project.

**Verdict (say it explicitly): Create | Absorb into <skill> | Automate
instead | Drop.** Only "Create" proceeds to Step 2.

## Step 2: Format Rules

- Frontmatter: exactly `name` + `description`. Nothing else.
- `name`: verb-first gerund, lowercase-hyphen, matches the directory
  (`creating-skills`, not `skill-creation`).
- `description`: third person, starts "Use when …", and states **only
  triggering conditions, never process. Include symptoms, errors, synonyms,
  and "about to violate" moments. Limit it to 30 words and 200 characters.
- Body: Overview (core principle in 1-2 sentences) → When to Use → the
  process → Quick Reference / tables → Common Mistakes.
- Context budget: always-loaded files ≤150 words; frequently loaded files
  normally ≤1,000 words; rare files ≤2,500. A higher file ceiling needs a
  measured workflow limit and reason in `tests/check-skill-budgets.py`.
  An unconditional sibling counts in its parent's budget. A conditional
  sibling needs an observable `Load when` trigger and its own ceiling.
  Never `@`-link references because that force-loads them.
- Cross-reference skills by namespace (`chimera:<name>`), never by bare
  path.
- **User agnostic.** Skills, agents, commands, and templates speak in role
  terms ("you", "your human partner", "the analyst", "the maintainer") —
  never a personal name, and never a reference to a past conversation
  ("as agreed", "per our discussion"). Decisions are recorded with a role
  and a date.

## Step 3: Match the Form to the Failure

Match the form to the observed failure:

| Failure you observed | Form to write |
|---|---|
| Agent knows the rule but rationalizes past it (discipline) | Iron Law + spirit-vs-letter clamp + rationalization table + red flags |
| Output is the wrong shape | **Positive recipe**: state what the output IS — its parts, in order. No prohibition lists |
| Agent omits an element | Required slot in a template ("a plan without a stopping rule is incomplete") |
| Behavior should differ by situation | Conditional keyed to an observable predicate ("if `docs/system-design.md` exists…") |

Avoid nuance clauses that reopen negotiation and exemption clauses that do
not scope reliably.

For discipline skills, build the prohibition stack from the
enforcement catalog in the research doc — and populate rationalization
tables **only with observed excuses**, never invented ones.

## Step 4: Test Before Deploy

```
NO SKILL WITHOUT A FAILING BASELINE FIRST
```

This is TDD for new skills and edits:

1. **RED** — run the triggering scenario with a fresh agent *without* the
   skill (or with the edit reverted). Watch it fail. If the baseline
   doesn't fail, the skill teaches nothing — Drop it.
2. **GREEN** — same scenario with the skill loaded. The agent complies.
3. **REFACTOR** — capture each new rationalization verbatim; close the
   loophole; re-test.

Discipline skills additionally get at least one **pressure test**
(combine 3+: time pressure, sunk cost, authority, exhaustion) before
they're trusted.

When editing a chimera discipline skill: the Iron Law, spirit-vs-letter
line, rationalization table, and red flags are load-bearing structure —
trim entries with evidence, never delete the structure.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "The skill is obviously right, skip the baseline" | Obvious-to-you ≠ binding-on-an-agent. The baseline is 5 minutes; a wrong skill misleads every future session. |
| "It's just a small edit" | Edits change behavior. Re-run the scenario. |
| "I'll test it in real use" | Real use is production. You won't notice the failure until it costs a session. |
| "More detail makes it stronger" | Length is cost. Cut text that does not change behavior. |
| "This knowledge is too useful to drop" | Then it belongs in a findings doc or CLAUDE.md — the gate said it's not a *skill*. |

## Red Flags — STOP

- Writing a SKILL.md before stating a gate verdict
- A description that contains workflow steps
- A rationalization-table entry you never actually observed
- Creating a second skill that overlaps an existing one "for clarity"
- Deploying (committing) a skill no agent has failed without
