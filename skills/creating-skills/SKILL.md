---
name: creating-skills
description: Use when creating a new skill or editing an existing one - for chimera, a project, or global use - before writing or changing any SKILL.md content
---

# Creating Skills

> Synthesized from Anthropic's skill-creator guidance, Superpowers'
> writing-skills (Jesse Vincent, MIT), and ECC's learn-eval quality gate
> (affaan-m, MIT). Deep reference: the
> [superpowers deep-dive](../../docs/research/2026-07-29-superpowers-deep-dive.md)
> — enforcement catalog (§c) and format conventions (§f).

## Overview

**Core principle:** a skill is code that shapes agent behavior, not prose.
It earns its context cost or it doesn't ship.

Create a todo per step below; complete them in order.

## Step 1: The Gate — should this be a skill at all?

Answer before writing anything:

1. **Overlap scan.** Grep existing skills — this project's `.claude/skills/`,
   chimera's `skills/`, `~/.claude/skills/` — for the same ground.
   Absorbing into an existing skill beats creating a near-duplicate.
2. **Mechanical constraint?** If a regex, linter, formatter, or hook can
   enforce it, automate it. Documentation is for judgment calls only.
3. **Repeated situation?** One-off knowledge belongs in findings docs or
   the project CLAUDE.md, not a skill.
4. **Placement.** Project-specific conventions → project `.claude/skills/`.
   Universal workflow/technique → global or chimera. Uncertain → project
   (promote later; demoting a global skill is harder).

**Verdict (say it explicitly): Create | Absorb into <skill> | Automate
instead | Drop.** Only "Create" proceeds to Step 2.

## Step 2: Format Rules

- Frontmatter: exactly `name` + `description`. Nothing else.
- `name`: verb-first gerund, lowercase-hyphen, matches the directory
  (`creating-skills`, not `skill-creation`).
- `description`: third person, starts "Use when …", and states **only
  triggering conditions — never the process**. A description that
  summarizes the workflow becomes a shortcut agents take instead of
  reading the body (measured failure: a "…with code review between
  tasks" description caused one review where the body required two).
  Make it keyword-rich: symptoms, error strings, synonyms, "about to
  violate" moments.
- Body: Overview (core principle in 1-2 sentences) → When to Use → the
  process → Quick Reference / tables → Common Mistakes.
- Token budget: always-loaded skills < 150 words; frequently loaded
  < 200 lines; others < 500 lines. Move heavy reference material to
  sibling files loaded conditionally ("Load when: …"). Never `@`-link
  files — `@` force-loads at session start and burns context.
- Cross-reference skills by namespace (`chimera:<name>`), never by bare
  path.

## Step 3: Match the Form to the Failure

Pick the guidance form from the failure mode you are preventing — the
forms are not interchangeable (superpowers measured prohibitions
*backfiring* on output-shape problems):

| Failure you observed | Form to write |
|---|---|
| Agent knows the rule but rationalizes past it (discipline) | Iron Law + spirit-vs-letter clamp + rationalization table + red flags |
| Output is the wrong shape | **Positive recipe**: state what the output IS — its parts, in order. No prohibition lists |
| Agent omits an element | Required slot in a template ("a plan without a stopping rule is incomplete") |
| Behavior should differ by situation | Conditional keyed to an observable predicate ("if `docs/system-design.md` exists…") |

Two findings that override instinct: **no nuance clauses** ("don't X
unless it matters" reopens the negotiation and measurably degrades a
winning recipe) and **exemption clauses don't scope** ("this limit doesn't
apply to code blocks" still suppresses code blocks).

For discipline skills, build the prohibition stack from the
enforcement catalog in the research doc — and populate rationalization
tables **only with observed excuses**, never invented ones.

## Step 4: Test Before Deploy

```
NO SKILL WITHOUT A FAILING BASELINE FIRST
```

This is TDD for process documents, and it applies to **edits too**:

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
| "More detail makes it stronger" | Length is cost. Every line loads into context; agents skim long skills. Cut to what changes behavior. |
| "This knowledge is too useful to drop" | Then it belongs in a findings doc or CLAUDE.md — the gate said it's not a *skill*. |

## Red Flags — STOP

- Writing a SKILL.md before stating a gate verdict
- A description that contains workflow steps
- A rationalization-table entry you never actually observed
- Creating a second skill that overlaps an existing one "for clarity"
- Deploying (committing) a skill no agent has failed without
