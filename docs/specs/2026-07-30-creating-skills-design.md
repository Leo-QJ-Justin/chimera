# creating-skills — Task Spec

**Mode:** build · **Approved:** maintainer, 2026-07-30 · **Roadmap:** n/a (chimera repo task)

## Goal

One slim skill, `chimera:creating-skills`, so chimera is self-sufficient
for skill authoring and the external `skill-creator` plugin can be
disabled (plugin-minimalism: chimera + as few external plugins as
possible).

## Behavior

Triggered when creating a new skill or editing an existing one (chimera's
own, project-level, or global). Walks four steps, synthesized from three
sources rather than lifted from any:

1. **The gate** (from ECC `/learn-eval`): should this be a skill at all —
   overlap scan against existing skills, absorb-over-duplicate, "automate
   mechanical constraints instead of documenting them", placement
   (project vs global), verdict: Create | Absorb | Automate | Drop.
2. **Format rules** (Anthropic + superpowers, convergent): two-field
   frontmatter; description = triggering conditions only, never the
   process; verb-first gerund names; token budgets; conditional reference
   loading; no `@`-links.
3. **Match the form to the failure** (superpowers, measured): discipline
   failure → prohibition stack; wrong-shaped output → positive recipe;
   omission → required slot; conditional → observable predicate. No
   nuance clauses.
4. **Test before deploy** (superpowers): no skill without a failing
   baseline first; pressure-test discipline skills; edits re-test.

Deep material is referenced, not duplicated:
[superpowers deep-dive](../research/2026-07-29-superpowers-deep-dive.md)
(enforcement catalog §c, format conventions §f).

## Interfaces / files

- Create: `skills/creating-skills/SKILL.md` (~150 lines)
- Modify: `skills/using-chimera/SKILL.md` — one routing row ("Creating or
  editing a skill"); stays ≤ 70 lines
- Modify: `README.md` (contents list 8→9 skills), `CHANGELOG.md` ([1.1.0]),
  `.claude-plugin/plugin.json` + `marketplace.json` (version 1.1.0)
- Modify: `docs/specs/2026-07-29-workflow-inventory.md` — add W12
  (create/edit a skill) so the artifact stays traceable

## Edge cases

- Skill-worthiness gate must fire *before* any authoring — the failure
  mode is enthusiasm-driven skill sprawl (the 281-skill cautionary tale).
- Editing an existing chimera discipline skill must preserve its Iron
  Law / rationalization-table structure (already a spec §9 rule; this
  skill is where that rule now lives operationally).

## Testing

Structural verification (frontmatter, required sections, line budgets,
routing row present, no dangling refs) + full hook test suite. Behavioral
pressure-testing of this skill itself is deferred to the v1.x eval work
(consistent with spec §9).

## Self-review

Placeholders: none. Consistency: name `creating-skills` used throughout;
routing row matches. Scope: single skill + registration touches — one
plan. Ambiguity: verdict vocabulary fixed (Create/Absorb/Automate/Drop).
