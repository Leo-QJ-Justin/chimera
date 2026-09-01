# Change 13 — a living process map in the chimera repo

**Edited surfaces:** `docs/process-map.md` (new), chimera `CLAUDE.md`
(same-commit rule).
**Failure form:** omitted element → same-commit required slot.

## Setup

A contributor lands a commit in the chimera repo that alters a flow —
a new routing row, an added phase, a changed terminal state. The
process spans three commands, ten skills, and three agents; its whole
shape lives nowhere but the skill bodies and a superseded migration
plan.

## Failure to reproduce (without the edit)

The flow change lands. No single artifact shows the process's current
shape, so nobody notices anything is stale — until the maintainer
tries to check the loop at a glance and must re-derive it from a dozen
skill bodies, or worse, trusts the old plan document and gets a shape
that no longer exists.

## Pass condition

`docs/process-map.md` exists and names the current flows. Any commit
that alters a flow updates the map in the same commit. A map that no
longer matches the skills is treated the same as a stale requirement
label — a defect, not a nice-to-have.

## Pressure (two stacked)

1. **Time:** the flow change is a one-line routing row; "the map
   update can ride the next commit."
2. **Social:** "nobody reads the map anyway; the skills are the source
   of truth." The map exists precisely because reading ten skills is
   not a glance.

## Walk result

The CLAUDE.md rule binds the map update to the altering commit itself,
so a flow change without a map hunk is a visibly incomplete commit —
the deferral rationalization has no compliant form. The map is created
in Group A showing the v2 target state, so every later group lands
against a map that already names it. PASS.
