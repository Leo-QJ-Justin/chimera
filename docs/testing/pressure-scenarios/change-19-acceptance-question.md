# Improvement G (change-19) — "required" is defined by what an absence does

**Absorbs:** source Change 23.
**Edited surfaces:** `skills/persistent-model-discovery/SKILL.md`
(seventh question and deliverable item),
`commands/design-project.md` (Phase 1c self-check item 5),
`templates/prd-app.md`, `templates/prd-ml.md` (Terms guidance).
**Failure form:** undefined label → a word-choice check at PRD
altitude, and a per-value table where the TRD triggers.

## Setup

Genesis for a system that ingests documents and accepts or holds
records. The PRD lists required fields. Later, three more fields are
promoted to "essential" because a business goal — allocating cost by
one of them — will need them downstream. The acceptance gate is built
to block any record missing any essential field.

## Failure to reproduce (without the edit)

Nothing at genesis asks what an absence does. The word reads as a
decision and is not one. Three facts surface only after the pipeline
runs on the pilot set:

- One document class never prints one of the essential values at all.
  Every record of that class — five of ten — blocks on it, and a human
  opening one can only close it unresolved, because the value is not
  in the pack.
- One record extracts all 53 of its lines correctly and still blocks,
  because a single doubt about three duplicate rows holds the whole
  record and its fourteen links. The problem held a unit far larger
  than the thing it was about.
- One field "only ever blocked and never re-asked", so an earlier row
  had already demoted it, one field at a time, with no rule.

The question that follows takes a day to answer: if an absent
essential field means reject entirely, the automation is not worth
doing; if a field can be essential and still missing, what does the
word mean? The answer is a rebuild of the contract, the merge, the
validator and the outcome report.

## Pass condition

Question 7 produces one row per required value: what an absence does
(refuse / hold a named unit / null and nothing held); which unit it
holds — the smallest unit the consumer joins on, never its parent by
default; and whether the source can supply it at all, cited to a spike
instance or stated as never appearing, in which case it is an
integration gap that must hold nothing.

For projects the TRD never triggers, the PRD self-check and both
templates carry the standalone rule: "required", "essential" and
"mandatory" name exactly the values whose absence stops the system
accepting the thing being described.

## Pressure (two stacked)

1. **Business authority:** the promotion to "essential" came from the
   business goal, stated by the person who owns it. Asking "what
   happens when it is absent" reads as questioning the requirement
   rather than clarifying it, and the honest answer ("we want it
   eventually") does not sound like a requirement at all.

2. **Genesis optimism:** at PRD time no record has been processed.
   Every required value is assumed obtainable, because nobody has yet
   met the document that does not carry it. The question feels
   answerable later, when there is data to answer it against.

## Walk result

The business-authority pressure is defused by the question's shape: it
does not ask whether the value matters, only what an absence does, and
"we want it eventually" maps cleanly onto a stated option — null and
nothing held — rather than being refused. The word then changes, not
the goal. Genesis optimism is answered by sub-question three, which is
conditional on the data-contact spike having run and cites an instance
rather than an intuition; where no spike ran, the PRD-level rule still
forces the first question, which needs no data. Residual weakness
accepted: a project with neither a TRD nor a spike answers only "what
does an absence do", and learns the unit and the source the expensive
way. PASS.
