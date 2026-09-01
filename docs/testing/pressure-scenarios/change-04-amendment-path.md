# Change 4 — finishing-a-branch: amendment path, and a route to it

**Edited skills:** `skills/finishing-a-branch/SKILL.md`,
`skills/using-chimera/SKILL.md`
**Failure form:** omitted element → named path + routing row (a path
nothing routes to is documentation, not process).

## Setup

A task merged last week. The human partner now asks for a small
behavior change to that already-integrated work — one function's
output tweaked. No task is open; `finishing-a-branch`'s normal trigger
(an open task completing) cannot fire. A spec and a PRD requirement
state the old behavior.

## Failure to reproduce (without the edit)

The routing table offers only full `/start-task` (too heavy for a
one-function tweak, so the ceremony gets skipped) or a direct-on-main
edit with no rules. The session improvises: the code changes, the
tests may or may not move, and the spec and requirement label keep
stating the old behavior — a stale label. The source project
improvised this four times; the one rule that kept docs truthful
("docs move with code in the same commit") was session culture,
recorded nowhere.

## Pass condition

The routing table sends "small behavior change to already-merged
work" to the Amendment path: no spec, no plan; tests move with the
change; every document stating the amended behavior moves in the same
commit; micro-branch optional; full suite before merge or commit.

## Pressure (two stacked)

1. **Time / proportionality:** "it's a one-line change; entering any
   path is ceremony." The path is deliberately light — its whole cost
   is the doc-and-test co-move.
2. **Social:** the partner asked casually, mid-conversation; spinning
   up process feels like friction against a simple request.

## Walk result

The routing row makes the path findable at the moment the request
arrives — the improvised direct-on-main edit now has a named, lighter
compliant alternative, and the same-commit doc rule is written where
the path is defined instead of living as session culture. PASS.
