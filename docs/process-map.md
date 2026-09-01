# Chimera process map

> The current shape of the whole loop. Updated in the same commit as
> any change that alters a flow. (Ch. N) marks the v2 change that
> introduced an element.

## 1. Project genesis — /design-project

Phase 0  TYPE             project type; existing repo?; brainstorm/distill
Phase 1  DISCOVER         brainstorm: problem, users, consumers
   ↓
Phase 1a DATA-CONTACT SPIKE   (Ch. 2) fires when a real corpus or
   artifact format exists:
   pin samples → name the priority authority doc →
   dispatch corpus-profiler (mechanical profile + handoff
   sections; judgment returned as questions) →
   close decision-blocking evidence gaps →
   human + main agent write the decision brief per the
   "profile → brief" recipe in writing-comparative-reports
   (population join, constraint move, reference implementation,
   bidirectional grounding, live conflicts, evidence labels)
   ↓
Phase 1b BIND             (Ch. 8) convert evidence into commitments,
   each as evidence → constraint → implications:
   • format/input requirements   • scope boundaries
   • persistent model — if external consumers / audit trail /
     migration-cost triggers fire → persistent-model-discovery
     skill → docs/technical-requirements.md → human approval
     (untriggered: one line in the PRD, no file)
   self-check: commitments trace to evidence; violators have
   dispositions (Ch. 11)
   ↓
Phase 1c PRD              written against brief + commitments;
                          cites them, never re-litigates them;
                          self-check: cited commitments exist,
                          FR IDs contiguous (Ch. 11)
Phase 2  ARCHITECTURE     ADRs; one-line Tier-1 ADR points at the
                          TRD when one exists (Ch. 8, 11)
Phase 3  SYSTEM DESIGN    preamble states grain / immutability /
                          consumers per the TRD, verbatim (Ch. 8, 11)
Phase 4  ROADMAP          queue of rows; gate rows; Realizes column
Phase 5  SCAFFOLD         skeleton; /new-project; commit genesis

## 2. Build-mode task — /start-task

designing-tasks:
  explore context → re-present FR contents for re-confirmation
    (Ch. 1)
  clarifying questions → correctness-path heuristics and scope
    renegotiations are ASKED, never only recorded (Ch. 7)
  spec carries: Decisions section (Ch. 1) + flow sketch against the
    depth budget (Ch. 6)
  STE register; notation defined at first use (Ch. 3)
   ↓
writing-plans:
  plan carries an empty ## Deviations section (Ch. 5)
   ↓
test-driven-development (execution):
  deviations logged in ## Deviations at the moment they are made
    (Ch. 5)
   ↓
verifying-before-done
   ↓
finishing-a-branch:
  code-reviewer briefed with spec + plan constraints + the
    deviations list framed as questions (Ch. 5)
  → green suite → menu (merge / PR / keep)

## 3. Exploration-mode task — /start-task

designing-tasks → research brief with decision line
   ↓
exploring-reproducibly:
  pin snapshot → eda-profiler (one tabular dataset) or
  corpus-profiler (heterogeneous corpus) (Ch. 2)
  findings doc closes with Decision + Constraint + Implications on
  every adopt, or "no design consequence" (Ch. 9)
   ↓
code-reviewer (exploration rubric, checks the closure) (Ch. 9)
   ↓
finishing-a-branch: findings merge; experiment code archived

## 4. After the loop closes

Small behavior change to already-merged work
   → Amendment path in finishing-a-branch (Ch. 4), routed from
     using-chimera: no spec, no plan; tests move with the change;
     every doc stating the amended behavior moves in the same commit

## 5. The learning loop (chimera improving chimera)

Field use accumulates friction
   → /retrospect (Ch. 12): collect friction events → quality-gate
     (observed, reusable, overlap grep, form check) → verdicts →
     improvement spec in docs/
   → implement in the chimera repo: each change pressure-tested
     against its own failure story before landing (Ch. 10)
   → this map updated in the same commit as any flow change (Ch. 13)
