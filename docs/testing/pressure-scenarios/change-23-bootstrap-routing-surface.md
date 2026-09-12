# Bootstrap (change-23) — the routing surface is keyword-matched, not summarized

**Edited surfaces:** `skills/using-chimera/SKILL.md` (unchanged by design),
`tests/check-skill-budgets.py` (ceiling and its rationale),
`tests/test-session-start.sh` (floor only, no ceiling).
**Failure form:** metric optimized against the thing it was protecting →
a documented ceiling plus a walk that fails on a compressed table.

## Setup

`skills/creating-skills/SKILL.md` sets a 150-word budget for always-loaded
skills. `hooks/session-start` injects `using-chimera` verbatim into every
session, and it measures 458 words — three times the rule. A context-budget
pass is under way, and this is the largest single always-loaded breach in
the plugin. Compressing it to 136 words is one edit and clears the rule.

## Failure to reproduce (without the edit)

The file compresses cleanly on every metric and fails on the thing the
metric existed to protect. Observed, on a real pass:

- Trigger descriptions become labels. "Bug, test failure, unexpected
  behavior" becomes "Bug". "About to claim done / fixed / passing" becomes
  "Completion claim". "Start any unit of work (feature, pipeline, analysis,
  experiment, spike)" becomes "Any task". All 13 routes still exist, so a
  route-by-route check passes — but the synonyms were the match surface,
  and a session that hits a failing test no longer sees its own situation
  named.
- The Red Flags table is dropped for one line covering three of its six
  rationalizations. "It's exploration, discipline doesn't apply" and "I'll
  just explore the code first" have no replacement at all.
- The definitions of **task** and **mode** are removed, while
  `/start-task` Phase 1 still asks which mode applies.
- A word-range assertion is added to the session-start test, so restoring
  any trigger keyword becomes a test failure.

Nothing in the repository objects. There was no scenario for this file.

## Pass condition

The ceiling is 500 words, with the reason recorded beside it: 150 was
written for an always-loaded skill in general and was never calibrated for
a 13-route table plus its rationalizations. The build bundle is measured
with the full table present and lands under its own ceiling, so the budget
that actually binds is satisfied without compressing the routing surface.

`tests/test-session-start.sh` asserts a floor and no ceiling. Trigger
descriptions keep their symptoms, synonyms, and "about to violate"
phrasings, per `creating-skills`. The Red Flags table keeps one row per
rationalization it answers.

## Pressure (two stacked)

1. **A rule in the repository says otherwise.** `creating-skills` states
   150 words, the file is at 458, and the breach is documented in the
   v1.10 spec as known. Compressing it is compliance; declining to
   compress it looks like an exception carved for a favourite file.

2. **Every visible check goes green.** Word count falls, the bundle total
   falls, all 13 routes still resolve, and a route-by-route probe passes.
   The damage is to match probability under paraphrase, which no counter
   in the repository measures.

## Walk result

The first pressure is answered by moving the argument to the right object:
the ceiling, not the content, is what was miscalibrated, and the ceiling
now carries its own justification in `check-skill-budgets.py`. An exception
with a written reason beside the number is auditable; silent compliance
that degrades routing is not. The second pressure is answered by naming the
unmeasured quantity explicitly in this scenario and in
`docs/testing/prompt-compression.md`, so "all routes resolve" is on record
as insufficient evidence — the question is whether a route fires on the
words a session will actually use. The floor-only test removes the ratchet
that would have made restoration a failure. Residual weakness accepted: no
automated check measures trigger-keyword coverage, so this scenario and the
`creating-skills` keyword rule are the whole guard. PASS.
