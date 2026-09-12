# Chimera process map

> The current shape of the whole loop. Updated in the same commit as
> any change that alters a flow. (Ch. N) marks the v2 change that
> introduced an element; (v1.10 X) marks the v1.10 improvement, A to I,
> that introduced one; a bare (v1.10) marks the same release's context-
> budget pass, which changed what loads rather than what the loop does.

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
   NOTE: genesis runs no prior-art survey of its own — that trigger
   is deferred. Whenever writing-comparative-reports IS used on
   outside products or published methods, its guard applies: a
   mapping by cited instance + a ruled-out section; the survey
   proposes, the evidence decides (v1.10 I)
   ↓
Phase 1b BIND             (Ch. 8) convert evidence into commitments,
   each as evidence → constraint → implications:
   • format/input requirements   • scope boundaries
   • persistent model — if external consumers / audit trail /
     migration-cost triggers fire → persistent-model-discovery
     skill → docs/technical-requirements.md → human approval
     (untriggered: one line in the PRD, no file)
     seven questions: grain, immutability, corrections, consumers,
     scope, failure modes, acceptance — what an absence does, to
     which unit, and whether the source can supply it (v1.10 G)
   self-check: commitments trace to evidence; violators have
   dispositions (Ch. 11)
   ↓
Phase 1c PRD              written against brief + commitments;
                          cites them, never re-litigates them;
                          self-check: cited commitments exist,
                          FR IDs contiguous (Ch. 11);
                          "required" names exactly the values whose
                          absence stops acceptance (v1.10 G)
Phase 2  ARCHITECTURE     ADRs; one-line Tier-1 ADR points at the
                          TRD when one exists (Ch. 8, 11)
Phase 3  SYSTEM DESIGN    preamble states grain / immutability /
                          consumers per the TRD, verbatim (Ch. 8, 11)
Phase 4  ROADMAP          queue of rows; gate rows; Realizes column;
                          a row names its outcome, never its method,
                          and a held proposal is a cited note (v1.10 F)
Phase 5  SCAFFOLD         skeleton; /new-project; commit genesis

## 2. Build-mode task — /start-task

Phase 1: a row naming a parked branch re-validates its notes by
  trial rebase before design (v1.10 E)
   ↓
designing-tasks:
  explore context → re-present FR contents for re-confirmation
    (Ch. 1)
  clarifying questions → correctness-path heuristics and scope
    renegotiations are ASKED, never only recorded (Ch. 7); an
    accepted heuristic names an input it gets wrong (v1.10 A)
  a rule is presented as 3+ traced cases; a bulk artifact is
    produced one unit first and ruled on (v1.10 A)
  spec carries: Decisions section (Ch. 1) + flow sketch against the
    depth budget (Ch. 6)
  interfaces state the FORM of each value, not only its type;
    every aggregate ships the instances behind it (v1.10 C)
  STE register; notation defined at first use (Ch. 3)
   ↓
writing-plans:
  plan carries an empty ## Deviations section (Ch. 5)
  plan carries ## Preconditions: every external resource with the
    one command that proves it live (v1.10 E)
   ↓
Phase 4 opens (both modes): preconditions run BEFORE task 1; a
  failure stops the phase — renew / reorder / split (v1.10 E)
   ↓
test-driven-development (execution):
  writing-good-tests.md loads ONLY for mocks/fakes, helpers or
    cleanup, artifact tests, or nontrivial expected values (v1.10)
  deviations logged in ## Deviations at the moment they are made
    (Ch. 5)
   ↓
verifying-before-done
   ↓
finishing-a-branch:
  Step 0  code-reviewer briefed with spec + plan constraints + the
    deviations list framed as questions (Ch. 5); it proves
    new-behavior coverage by an executed mutation on a scratch
    copy — nothing moved = inconclusive (v1.10 H)
  Step 0b every Decisions entry marked task-local or written into
    its living document; a convention change gives every artifact
    holding the old answer a disposition (v1.10 D)
  Step 1  green suite → menu (merge / PR / keep)

## 3. Exploration-mode task — /start-task

Phase 1: a row naming a parked branch re-validates its notes by
  trial rebase before design (v1.10 E)
   ↓
designing-tasks → research brief with decision line
   ↓
writing-plans: experiment plan + stopping rule; ## Preconditions and
  an empty ## Deviations, as in build (Ch. 5, v1.10 E)
   ↓
Phase 4 opens (both modes): preconditions run BEFORE task 1; a
  failure stops the phase — renew / reorder / split (v1.10 E)
   ↓
exploring-reproducibly:
  playbook-stat-tests.md loads ONLY for an inferential claim, test
    selection, or a group judgment beyond the sample (v1.10)
  pin snapshot → eda-profiler (one tabular dataset) or
  corpus-profiler (heterogeneous corpus) (Ch. 2)
  findings doc closes with Decision + Constraint + Implications on
  every adopt, or "no design consequence" (Ch. 9)
  an aggregate whose instances cannot be listed is not verified
    (v1.10 C)
   ↓
code-reviewer (exploration rubric, checks the closure) (Ch. 9)
   ↓
finishing-a-branch: findings merge; experiment code archived

## 4. After the loop closes

Small behavior change to already-merged work
   → Amendment path in finishing-a-branch/post-loop-paths.md
     (Ch. 4), routed from
     using-chimera: no spec, no plan; tests move with the change;
     every ARTIFACT encoding the amended behavior moves in the same
     commit — docs, fixtures, labelled data, tests, prompts (v1.10 D)

Part of a task moves to a later row
   → Split path in finishing-a-branch/post-loop-paths.md: a named
     branch, never a stash; named in the inheriting row, the
     hand-off, and an execution amendment (v1.10 E)

## 5. The learning loop (chimera improving chimera)

Field use accumulates friction
   → /retrospect (Ch. 12): collect friction events → quality-gate
     (observed, reusable, overlap grep, form check) → verdicts →
     improvement spec in docs/
   → implement in the chimera repo: each change pressure-tested
     against its own failure story before landing (Ch. 10)
   → context cost is a gate too: tests/check-skill-budgets.py
     enforces per-file, per-description and whole-bundle budgets;
     a skill that cannot fit argues about its ceiling, never
     about its triggers (v1.10)
   → this map updated in the same commit as any flow change (Ch. 13)
