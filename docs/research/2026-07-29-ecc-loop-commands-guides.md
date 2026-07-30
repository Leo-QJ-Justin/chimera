# ECC Deep-Read: Feature-Development Loop, Agents, Guides, Templates, TDD

> Research artifact for chimera. Mined 2026-07-29 from
> `~/personal_projects/ECC` (everything-claude-code, by affaan-m).
> Purpose: source material for chimera's loop commands, the code-reviewer
> agent, CLAUDE.md templates, and the TDD-enforcement analysis. Sibling
> reports: [superpowers deep-dive](2026-07-29-superpowers-deep-dive.md),
> [ECC learning/hooks](2026-07-29-ecc-learning-hooks.md).

---

## (a) Command dossiers

### `/feature-dev` (50 lines) — the loop skeleton, remarkably thin
7 phases: Discovery → Codebase Exploration (code-explorer agent) →
Clarifying Questions (wait) → Architecture Design (code-architect agent,
wait for approval) → Implementation ("prefer TDD where appropriate" — one
sentence, optional) → Quality Review (code-reviewer agent) → Summary.
Steal the 3-gate structure; note there is NO verification phase and NO
branch/PR finish.

### `/code-review` (290 lines) — most polished command (adapted from PRPs-agentic-eng)
Dual-mode via $ARGUMENTS (PR number/URL → PR mode; else local).
Local: GATHER (git diff, stop if empty) → REVIEW (read changed files IN
FULL; Security CRITICAL / Quality HIGH / Practices MEDIUM) → REPORT.
PR: FETCH → CONTEXT (CLAUDE.md, planning artifacts, PR intent) → REVIEW
(full file contents at PR head; 7 categories) → VALIDATE (detect project
type; run typecheck/lint/test/build) → DECIDE → REPORT artifact
(`.claude/reviews/pr-N-review.md`) → PUBLISH (gh pr review + inline
comments) → OUTPUT.
**Decision matrix** (copy verbatim): zero CRIT/HIGH + validation passes →
APPROVE; only MED/LOW → approve w/ comments; any HIGH or validation failure
→ REQUEST CHANGES; any CRITICAL → BLOCK. Draft PR → always COMMENT.
Also steal: CAPS phase names; "read the full file, not just diff hunks";
Edge Cases trailer.

### `/checkpoint` (79 lines)
Git-stamp system: create (verify → stash/commit → log line with timestamp|
name|SHA) / verify (compare vs checkpoint: files, test pass rate, coverage
delta) / list / clear (keep 5). Contains a dangling reference to removed
`/verify` (→ legacy shim). Low priority for chimera.

### `/build-fix` (67 lines)
Detect build system (indicator table) → parse/group errors by file, sort by
dependency order → fix ONE at a time (read 10 lines context → root cause →
minimal edit → re-run) → **guardrails: STOP and ask if a fix introduces
more errors than it resolves; same error persists after 3 attempts; fix
needs architectural change; missing dependencies.** The 3-attempt circuit
breaker is the single most useful guardrail in the repo (adopted into
chimera /start-task Phase 4).

### `/plan` (206 lines)
"Run inline by default. Do not call the Task tool or any subagent by
default" (defensive: works without agent files). 4 input modes (PRD path →
artifact mode; markdown → reference; free text → conversational; empty →
clarification). **Pattern Grounding** (best idea, adopted into chimera
writing-plans): before planning, capture one codebase example per category —
naming, error handling, logging, data access, tests — with file:line; "If no
similar code exists, state that explicitly. Do not invent a pattern."
Plan artifact: Summary / Patterns to Mirror / Files to Change (CRUD table) /
Tasks (Action, Mirror, Validate) / Validation bash / Risks / Acceptance
checkboxes. Hard gate: "will NOT write any code until you explicitly
confirm."

### `/prp-implement` (385 lines) — the real implementation engine
Golden Rule: "If a validation fails, fix it before moving on. Never
accumulate broken state."
- Phase 2 PREPARE — **branch decision table (adopted into chimera Phase 0)**:
  on feature branch → use it; on main + clean → `git checkout -b
  feat/{name}`; **on main + dirty → STOP, ask stash or commit**; worktree →
  use it. Then `git pull --rebase`.
- Phase 3 EXECUTE: read MIRROR reference first → implement → typecheck after
  EVERY file change → log `[done] Task N`; deviations recorded WHAT+WHY.
- Phase 4 VALIDATE — 5 levels: static analysis → unit tests ("every function
  needs at least one test"; "fix the implementation, not the test, unless
  the test is wrong") → build → integration (server start/health-poll/kill
  template) → edge cases.
- Phase 5 REPORT: Assessment-vs-Reality table (predicted vs actual
  complexity/confidence/files); archive plan to completed/.
- Success criteria as named flags (TASKS_COMPLETE, TYPES_PASS, …).

### `/pr` (185 lines) — finish-branch
VALIDATE precondition table (not on base branch; clean dir; commits ahead;
no existing PR) → DISCOVER (PR template search order; conventional-commit
title from dominant commit type; link planning artifacts) → PUSH (rebase on
divergence; stop on conflicts) → CREATE (fill template, N/A rather than
delete sections) → VERIFY (gh pr checks) → OUTPUT.
**"Use `git push --force-with-lease` (never `--force`)"**; >20 files → warn,
suggest splitting.

### Others
`/prp-commit` (112): natural-language staging table (blank→add -A;
"except tests"→add-then-reset globs; "the auth changes"→cross-reference
diff). Commit rules: imperative, <72 chars, WHAT not HOW.
`/refactor-clean` (85): dead-code removal, one deletion at a time with full
test re-run; SAFE/CAUTION/DANGER tiers; "don't refactor while cleaning."
`/quality-gate` (52): formatter-only, coupled to ECC's hook dispatcher —
skip. `/project-init` (86): see templates section.

---

## (b) Agent dossiers

All 67 agents: uniform frontmatter (name/description/tools/model) + an
8-line "Prompt Defense Baseline" boilerplate (skip it).

- **`planner`** (222, opus, Read/Grep/Glob — read-only by construction):
  plan template with per-step Action/Why/Dependencies/Risk; **Sizing and
  Phasing**: Phase 1 minimum viable → Phase 4 optimization, "each phase
  mergeable independently"; meta red-flags ("plans with no testing
  strategy", "steps without file paths", "phases that cannot be delivered
  independently"); 75-line worked example (few-shot by demonstration).
- **`architect`** (221, opus): trade-off analysis (every decision documents
  Pros/Cons/Alternatives/Decision); ADR template; ~60% overlap with planner;
  back half is the author's own stack leaking in (dead weight).
- **`code-architect`** (81, sonnet) — the one /feature-dev calls; the
  keeper: "choose the simplest architecture that meets the requirement";
  "avoid speculative abstractions unless the repo already uses them"; build
  sequence types → core → integration → UI → tests → docs (note: test-LAST —
  architecturally contradicts TDD).
- **`code-explorer`** (79, sonnet): entry points → execution paths → layers
  → patterns → dependencies; output ends with **Follow / Reuse / Avoid**
  recommendations (converts exploration into planning input).
- **`code-reviewer`** (322, sonnet) — **best file in the repo; adopted
  nearly wholesale into chimera's agent**:
  - Confidence-based filtering: report only >80% confident; consolidate
    similar issues; skip stylistic preferences.
  - Pre-report gate, 4 questions (exact line? concrete failure mode —
    input/state/outcome? read surrounding context? severity defensible?);
    any no → downgrade or drop. "If you cannot name the trigger, you are
    pattern-matching, not reviewing."
  - HIGH/CRITICAL require proof: snippet + failure scenario + why existing
    guards don't catch it; else demote.
  - **"It Is Acceptable And Expected To Return Zero Findings"**: "a clean
    review is a valid review. Manufactured findings, filler nits,
    speculative 'consider using X'… are the primary failure mode of LLM
    reviewers."
  - 12-entry false-positive skip list (each with why it's usually wrong):
    error handling the framework handles; input validation on internal
    functions ("trace at least one caller before flagging"); magic numbers
    200/404/60/1024; long functions that are exhaustive switches/config/
    test tables; JSDoc on self-describing helpers; const-vs-let without
    reading the whole function; null deref past a guard; N+1 on fixed
    cardinality; intentional fire-and-forget; TS-in-JS-repo; hardcoded test
    fixtures; security theater (Math.random non-crypto).
  - Closing heuristic: "Would a senior engineer on this team actually
    change this in review? If no, skip."
  - Verdict required: Approve (incl. zero findings) / Warning / Block;
    "Do not withhold approval to appear rigorous."
  - Defers to project CLAUDE.md conventions; "match what the rest of the
    codebase does."
- **`tdd-guide`** (101, sonnet, has Write/Edit — no structural separation):
  6-step red/green cycle; 8 mandatory edge cases (null, empty, invalid
  types, boundaries, error paths, races, 10k+ items, unicode); eval-driven
  addendum (pass@1/pass@3, pass^3 for release-critical).
- **`code-simplifier`** (54, sonnet): preserve behavior exactly; "unwind
  over-abstracted single-use helpers" (rare anti-abstraction instruction —
  correct counterweight for LLM code); 54 lines does the job — evidence
  agents don't need to be long.

---

## (c) Guide recommendations (the author's own advice)

### Shortform guide (431 lines)
- Hierarchy: "Skills are the primary workflow surface… commands are legacy
  slash-entry compatibility. The durable logic should live in skills."
- **Context management is the #1 theme**: "Your 200k context might be 70k
  with too many tools enabled." Rules of thumb: <10 MCPs enabled, <80 tools
  active; author has 14 plugins installed but "only 4-5 enabled at a time."
- Key takeaways verbatim: "Don't overcomplicate — treat configuration like
  fine-tuning, not architecture"; "Context window is precious"; parallel via
  forks/worktrees; automate the repetitive with hooks; scope subagents.
- His working set: 9 agents (planner, architect, tdd-guide, code-reviewer,
  security-reviewer, build-error-resolver, e2e-runner, refactor-cleaner,
  doc-updater), 8 rules files, small hook set (prettier-on-save,
  tsc-on-save, console.log warnings, block stray .md writes).

### Longform guide (354 lines)
- **Replace MCPs with CLI + skills** (GitHub MCP → `/gh-pr` wrapping `gh`).
- Memory: session files must contain "what worked (verifiably), what was
  attempted and failed, what's left"; new file per session; disable
  auto-compact, compact manually at logical intervals; Stop hook over
  UserPromptSubmit (latency).
- System-prompt injection: `claude --system-prompt "$(cat memory.md)"`;
  "system prompt > user messages > tool results" authority ordering.
- Model routing table: haiku exploration/simple edits/docs; sonnet
  multi-file implementation/PR review (default for 90%); opus architecture/
  security/complex debugging. "Upgrade when first attempt failed, 5+ files,
  architectural, or security-critical."
- **The orchestrator pattern** (= chimera's loop, stated by the author):
  RESEARCH → PLAN → IMPLEMENT (tdd) → REVIEW → VERIFY; "each agent gets ONE
  input, produces ONE output; outputs become inputs; never skip phases;
  /clear between agents; store intermediate outputs in FILES."
- Sub-agent context problem: "the sub-agent only knows the literal query,
  not the PURPOSE… pass objective context, not just the query"; iterative
  retrieval max 3 cycles.
- Parallelization: "minimum viable amount"; 3-4 tasks max.
- pass@k vs pass^k: "pass@k when you just need it to work; pass^k when
  consistency is essential."
- README: "Start with the workflow you need, not the full catalog";
  "Optimize the context window. Persist everything else"; "A result is not
  just code. It's a trail of evidence."
- ECC's own `minimal` install profile drops the hook runtime entirely.

---

## (d) Template findings

- `examples/CLAUDE.md` (109 lines, project-level): reusable skeleton =
  Overview → Critical Rules (organization: 200-400 lines/file, 800 max;
  style; testing; security) → File Structure → Commands → Git Workflow.
  Stack-opinionated filler otherwise.
- `examples/user-CLAUDE.md` (109 lines): **user-level CLAUDE.md as an
  index/router, not a content dump** — points at modular rules files and
  agent tables; the Knowledge Capture block generalizes well (personal
  notes → memory; project knowledge → project docs; don't duplicate; ask
  before creating new top-level docs).
- **`/project-init` (commands/project-init.md:69-79) — the actual minimal
  answer, contradicting the 109-line template**: a starter CLAUDE.md should
  contain ONLY detected build/test/lint/dev commands + repo-specific notes.
  "Never replace an existing CLAUDE.md without showing a diff and receiving
  approval"; merge/append, never overwrite; dry-run by default. (Adopted
  into chimera /new-project.)
- `scaffolds/` is Cursor-adapter plumbing only — nothing loop-related.

---

## (e) TDD mechanism analysis — the enforcement-tier finding

**Confirmed: ECC's TDD is suggestive, not enforced.** Encoded on four
surfaces (skill `tdd-workflow` 584 lines; agent tdd-guide; rules
common/testing; deprecated command shim) — none enforcing:

1. **No hook gates TDD.** All 14 hooks enumerated; none checks for a failing
   test before allowing Edit/Write. gateguard-fact-force is an investigation
   gate, not a RED gate. The only Stop hook is format/typecheck.
2. The strongest language lives in documents the model chooses to follow
   ("Do not edit production code until this RED state is confirmed" — a
   string in a markdown file; the tool call is not intercepted).
3. Evidence mechanism is self-reported (TDD Evidence Report; "do not invent
   PASS results" — the only defense against fabrication is an instruction
   not to fabricate).
4. Git checkpoints (commit after RED, after GREEN, reachability checks) are
   good anti-gaming ideas but are checks the model performs on itself.
5. Other surfaces actively weaken it: /feature-dev "prefer TDD where
   appropriate"; code-architect's build sequence is test-last;
   /prp-implement writes tests in Phase 4 AFTER Phase 3 implements;
   tdd-guide has Write/Edit tools.
6. README claims enforcement it doesn't have.

**Three enforcement tiers** (the frame chimera's spec adopted):
- Suggestive: instructions in context — the model can violate silently.
- Procedural: workflow ordering + required artifacts + gates — violations
  leave visible gaps.
- Enforced: deterministic code outside the model (PreToolUse block) — the
  tool call fails; compliance is not consulted.

ECC has tier-3 machinery and applies it elsewhere (config-protection,
doc-file-warning, gateguard) — just never to TDD. **The minimum viable
tier-3 TDD gate** (chimera v1.1 candidate): PreToolUse on Edit|Write that
(a) allows test-glob paths unconditionally, (b) for source paths, checks a
session state file for a recorded RED observation (test command + non-zero
exit + timestamp within current task), (c) exits 1 with an actionable
message otherwise. ECC supplies the content (RED definitions, runtime vs
compile-time RED, edge cases, evidence schema, commit-reachability
anti-gaming); the gate itself must be built.

---

## Files to read first when improving chimera (top 5)

1. `ECC/agents/code-reviewer.md` — best file in the repo
2. `ECC/commands/prp-implement.md` — the real implementation loop
3. `ECC/skills/tdd-workflow/SKILL.md` — RED/GREEN definitions worth lifting
4. `ECC/commands/plan.md` — Pattern Grounding + artifact template
5. `ECC/the-longform-guide.md` — orchestrator, model routing, context
   discipline

**Do not copy**: Prompt Defense Baseline; architect.md's hardcoded stack;
/quality-gate; the 109-line CLAUDE.md template (trust /project-init);
planner/architect/code-architect triplication (pick code-architect);
scaffolds/. The repo's own advice it doesn't follow: "Don't overcomplicate"
— 2,506 files shipping 280 skills is the cautionary artifact attached to
its own good advice.
