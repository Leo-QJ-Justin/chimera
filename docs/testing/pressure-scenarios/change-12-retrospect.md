# Change 12 — /retrospect: formalize the learning loop

**Edited surfaces:** `commands/retrospect.md` (new),
`skills/using-chimera/SKILL.md` (routing row).
**Failure form:** wrong-shaped output → positive recipe (collect →
quality-gate → verdict → spec), plus a routing row.

## Setup

A project phase just completed under chimera. The run accumulated
friction: two post-merge corrections, one improvised ceremony, one
moment where the human interrupted genesis to force a step chimera did
not prescribe. The human asks "what should we change about the
process?"

## Failure to reproduce (without the edit)

The learning loop exists only as operator memory — it was executed by
hand twice (the v1 and v2 specs), improvising its format each time.
Without the operator remembering to run it, lessons evaporate; when it
does run, candidates skip the quality gate: hypothetical failures get
adopted, one-off project lessons get pushed into the plugin, new
skills get created where an existing one needed a row, and dropped
lessons vanish without a recorded reason and re-surface later.

## Pass condition

`/retrospect` is routed and produces the spec in the proven format:
friction events collected from history; each candidate gated
(observed not invented, reusable not one-off, overlap grep,
form check); a verdict per candidate with dropped ones listed and
reasoned; the spec written to the consuming project in STE register,
self-contained. The command never edits the plugin directly and never
runs automatically — retrospection is invoked, not hooked.

## Pressure (two stacked)

1. **Recency bias (time):** the freshest friction dominates; walking
   the full phase history feels redundant when "we know what went
   wrong."
2. **Builder's itch (momentum):** the fix is obvious mid-retro; the
   pull is to edit the plugin now instead of writing a gated spec for
   a separate approved task.

## Walk result

The recipe makes the gate mandatory before any verdict, and the
no-direct-edit rule separates diagnosis from surgery — the plugin edit
is its own approved task in the chimera repo, which is also where each
adopted rationale becomes a Change-10 pressure scenario. The rejected
automated alternative is recorded in the command itself, so the
"hook it" temptation meets a documented verdict. PASS.
