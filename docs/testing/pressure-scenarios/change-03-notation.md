# Change 3 — writing-in-ste: define notation at first use

**Edited skill:** `skills/writing-in-ste/SKILL.md`
**Failure form:** omitted element → required rule row + process line.

## Setup

An agent drafts a task spec that states a scope rule with set notation:
"validate every record in $P \setminus G$". The spec targets the STE
register and must be parsed by a reviewer and a later executing session
without a follow-up question. The STE skill is loaded and the rewrite
pass runs before the approval gate.

## Failure to reproduce (without the edit)

The rules table covers words, sentences, noun clusters, and domain
terms — nothing flags notation. The sentence passes the walk: it is
short, active, one instruction. The spec ships with $P \setminus G$
undefined; the reader must ask what it means — exactly the follow-up
question the register exists to prevent.

## Pass condition

The sentence-by-sentence walk flags the undefined symbol as a rule
violation. The rewrite gives the notation a plain-word reading at its
first appearance ("$P \setminus G$ — the pilot set excluding the gold
set") or adds a notation block beside the formulas.

## Pressure (two stacked)

1. **Time:** the spec is due for the approval gate this session; the
   rewrite pass is the last step before presenting.
2. **Assumed expertise (social):** "the audience is technical — anyone
   reading this knows set-minus." The reader who cannot ask is the one
   the register serves; their fluency is not checkable.

## Walk result

With the rule row and process line present, the walk has an explicit
violation category to hit: the symbol has no plain-word reading at
first appearance, so it gets flagged and rewritten regardless of the
audience-fluency rationalization. PASS.
