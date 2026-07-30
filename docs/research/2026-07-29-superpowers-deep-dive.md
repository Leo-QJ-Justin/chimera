# Superpowers Repo — Deep Mechanics Report

> Research artifact for chimera. Mined 2026-07-29 from
> `~/personal_projects/superpowers` (v6.2.0, HEAD `44c9b2d`, author Jesse
> Vincent / obra). Purpose: source material for chimera v1.0 skill lifting
> and for future v1.x improvements — consult this before re-reading the repo.
> Sibling reports: [ECC learning/hooks](2026-07-29-ecc-learning-hooks.md),
> [ECC loop commands/guides](2026-07-29-ecc-loop-commands-guides.md).

179 files. Skills total ~10,263 lines of markdown across `skills/`.

---

## (a) Per-skill dossier — all 14 skills

Every skill lives at `skills/<name>/SKILL.md`. Frontmatter is **exactly two
YAML fields** in every case: `name` (must equal the directory name;
letters/numbers/hyphens only) and `description` (third-person, starts with
"Use when…", max 1024 chars total frontmatter, target <500 chars). No other
frontmatter fields anywhere — no `allowed-tools`, no `version`.

### 1. `using-superpowers` — 62 lines
The bootstrap. Injected verbatim into every session by the SessionStart hook;
never invoked via the Skill tool.
- The Rule: invoke relevant/requested skills BEFORE any response or action —
  including clarifying questions. "If it turns out wrong for the situation,
  you don't have to use it" (lowers compliance cost).
- Before plan mode → brainstorming first. Announce "Using [skill] to
  [purpose]". "If it has a checklist, create a todo per item."
- Skill priority: process skills first, then implementation skills.
- Precedence chain: user instructions > skills > default behavior.
- Enforcement: `<SUBAGENT-STOP>` block (subagents ignore the bootstrap —
  anti-recursion); `<EXTREMELY-IMPORTANT>` 1% rule ("even a 1% chance a
  skill might apply → you ABSOLUTELY MUST invoke it… not negotiable");
  12-row red-flags rationalization table ("This is just a simple question" →
  "Questions are tasks. Check for skills."; "I remember this skill" →
  "Skills evolve. Read current version.").

### 2. `brainstorming` — 151 lines (+ visual-companion.md 298)
Description leads "You MUST use this before any creative work…" (the one
description violating its own "Use when…" convention — it's the acceptance
test for every harness port).
- 9-item checklist (todo per item, in order): explore context → offer visual
  companion just-in-time → questions ONE at a time → 2-3 approaches w/
  recommendation → present design in sections w/ per-section approval →
  write spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` +
  commit → spec self-review (placeholders/consistency/scope/ambiguity) →
  user review gate (scripted message) → invoke writing-plans.
- `<HARD-GATE>`: no implementation action until design presented and
  approved, "EVERY project regardless of perceived simplicity."
- Named anti-pattern: "This Is Too Simple To Need A Design."
- Terminal-state lock (stated twice): "The ONLY skill you invoke after
  brainstorming is writing-plans."
- Scope-decomposition rule for multi-subsystem requests. "YAGNI ruthlessly."
- Visual companion: zero-dep local HTTP+WS server for mockups; offer must be
  its own message; per-question browser-vs-terminal decision.

### 3. `writing-plans` — 168 lines
- Framing: write for an engineer with "zero context for our codebase and
  questionable taste… aversion to testing."
- Plans to `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`. Announce at
  start.
- Task right-sizing: "smallest unit that carries its own test cycle and is
  worth a fresh reviewer's gate." Bite-sized steps (2-5 min each) with real
  code in the plan.
- Mandatory header: `> For agentic workers: REQUIRED SUB-SKILL:` blockquote
  (the plan artifact itself re-triggers the workflow in future sessions) +
  Goal/Architecture/Tech Stack + `## Global Constraints` (copied verbatim
  from spec; later handed to reviewers as their attention lens).
- Task template: `**Files:**` (Create/Modify/Test), `**Interfaces:**`
  (Consumes/Produces with exact signatures), checkbox steps.
- **No Placeholders** banned-token list framed as "plan failures": TBD/TODO,
  "add appropriate error handling", "write tests for the above", "Similar to
  Task N", steps without code, references to undefined types.
- Self-review: spec coverage, placeholder scan, cross-task type consistency.
- Execution handoff: verbatim 2-option menu (SDD recommended / inline).

### 4. `executing-plans` — 64 lines (smallest)
Load plan → review critically → todos → execute exactly → verify → announce
→ finishing-a-development-branch. "STOP executing immediately when" blocker/
gaps/unclear/repeated failure. Self-demoting: "If subagents are available,
use subagent-driven-development instead." "Never start implementation on
main/master without explicit user consent."

### 5. `test-driven-development` — 320 lines (+ writing-good-tests.md 198)
The archetype discipline skill; took 6 RED-GREEN-REFACTOR iterations to
bulletproof (10+ observed rationalizations closed).
- **Iron Law** (fenced block): `NO PRODUCTION CODE WITHOUT A FAILING TEST
  FIRST`.
- **Spirit-vs-letter clamp** (the sentence that finally made it hold):
  "Violating the letter of the rules is violating the spirit of the rules."
- Loophole closure: "Write code before the test? Delete it. Start over. No
  exceptions: Don't keep it as 'reference' / Don't 'adapt' it / Don't look
  at it / Delete means delete."
- Cycle: RED → verify RED (MANDATORY) → GREEN → verify GREEN (MANDATORY) →
  REFACTOR. `<Good>`/`<Bad>` code pairs ×4.
- 10-row rationalization table (longest rebuttals in repo: "I'll test
  after", "Tests after achieve same goals", sunk-cost, "TDD will slow me
  down"); 13 red-flag thought-strings → "Delete code. Start over with TDD.";
  8-box verification checklist → "Can't check all boxes? You skipped TDD.";
  exceptions enumerated and human-gated.
- writing-good-tests.md (conditional load): every test names the break it
  catches; test the real thing; no mirror assertions; no change detectors.

### 6. `systematic-debugging` — 283 lines (+ 3 technique refs, creation log, 4 test files)
- **Iron Law**: `NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST`.
- Four phase-gated phases: (1) Root cause — read errors, reproduce, recent
  changes, instrument EVERY component boundary in multi-component systems,
  trace backward; (2) Pattern analysis — find working examples, read
  reference implementations COMPLETELY; (3) Hypothesis — ONE at a time,
  written down, minimal test; say "I don't understand X"; (4) Implement —
  failing test first (→ TDD), single fix, verify (→ verification skill).
- **3-fix breaker**: ≥3 failed fixes → STOP, question the architecture; "this
  is NOT a failed hypothesis — this is a wrong architecture."
- Unique technique: "your human partner's Signals You're Doing It Wrong" —
  lists the user's likely frustrated phrasings ("Stop guessing", "We're
  stuck?") as machine-readable triggers → return to Phase 1.
- CREATION-LOG.md documents the bulletproofing method: ALWAYS/NEVER not
  should; structural defenses; deliberate redundancy ("'NEVER fix symptom'
  appears 4 times"); pressure-test files (Emergency Production Fix $15k/min,
  Sunk Cost + Exhaustion, Authority + Social Pressure).

### 7. `subagent-driven-development` — 503 lines (largest) + 3 prompt templates + 3 scripts
Controller never writes code. Per task: implementer subagent → review package
→ task reviewer → fix loop (≤5 rounds; rounds 1-3 resume original
implementer, 4-5 fresh implementer on stronger model) → ledger entry. Then
whole-branch final review → fix wave → scoped re-review → finish.
- Ledger at `<repo>/.superpowers/sdd/<plan>/progress.md` — survives
  compaction; "trust the ledger and git log over your own recollection."
- Context hygiene: artifacts as files, not pasted text ("a real session's
  dispatch hit 42k chars, 99% pasted history"); 5-slot dispatch recipe;
  <15-line report contracts.
- Model selection per role; "always specify the model explicitly."
- Anti-pre-judging tripwire: "If the prompt you are writing contains 'do not
  flag', 'don't treat X as a defect', 'at most Minor', or 'the plan chose' —
  stop."
- Breaker at round 5: adjudicate each finding (reviewer wrong / real but
  inert / real and load-bearing → BLOCKED, report to human). "A silent
  discard is forbidden."
- Reviewer templates: "Do Not Trust the Report" (implementer rationales are
  claims); ADDRESSED/NOT ADDRESSED re-review verdicts ("'Attempted' is not
  addressed"); positive output recipes ("Your final message is the report
  itself: begin directly with the verdict").
- NOT lifted into chimera v1.0 (orchestration machinery beyond bare-minimum
  solo workflow) — but the ledger/context-hygiene/fix-loop patterns are the
  reference if v1.x ever adds orchestration.

### 8. `verification-before-completion` — 120 lines
- **Iron Law**: `NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE`.
- 5-step gate: IDENTIFY command → RUN full/fresh → READ full output →
  VERIFY → only then claim. "Skip any step = lying, not verifying."
- Claims-vs-evidence table (7 rows); red flags include "Great!/Perfect!/
  Done!" before verification; anti-paraphrase clause ("applies to exact
  phrases, paraphrases, synonyms, implications of success"); regression-test
  pattern includes revert-fix→must-fail→restore→pass.

### 9. `requesting-code-review` — 95 lines (+ code-reviewer.md 172 template)
Get BASE/HEAD SHAs → dispatch general-purpose subagent with the template
(4 placeholders) → act by severity; push back if reviewer is wrong.
Template: read-only review ("never move HEAD"); strengths first;
Critical/Important/Minor with file:line; explicit verdict required ("Ready
to merge? Yes|No|With fixes"); "Don't: say 'looks good' without checking /
mark nitpicks as Critical / review code you didn't read / avoid a verdict."

### 10. `receiving-code-review` — 205 lines
Polices tone: READ → UNDERSTAND → VERIFY against codebase → EVALUATE →
RESPOND → IMPLEMENT one at a time. Forbidden: "You're absolutely right!",
"Great point!", ANY gratitude ("about to write 'Thanks'? DELETE IT. State
the fix instead."). External reviewers get 5-check skepticism; YAGNI check
greps for actual usage before implementing suggested "professional"
features. Unclear feedback → stop, clarify all items first.

### 11. `using-git-worktrees` — 167 lines
Detect existing isolation (GIT_DIR vs GIT_COMMON_DIR + submodule guard) →
consent gate → native harness tools preferred ("git worktree add when you
have a native tool creates phantom state") → fallback `.worktrees/` with
mandatory `git check-ignore` verification → project setup → verify clean
baseline (run tests before starting).

### 12. `finishing-a-development-branch` — 201 lines
Green suite first → detect environment (capture WORKTREE_PATH before any cd)
→ confirm base branch → verbatim 3-option menu (merge locally / push+PR /
keep as-is) → merge path re-runs tests on merged result → cleanup only
self-created worktrees. **Typed `discard`** quarantine for destruction
("'Yeah, get rid of it' counts as confirmation" → "Only the typed word
`discard` authorizes deletion"). 9-row rationalization table guarding the
human decision point ("They obviously want it merged" → "Integration is
your human partner's decision. Present the menu and wait.").

### 13. `dispatching-parallel-agents` — 167 lines
2+ independent tasks → focused agent briefs (scope/goal/constraints/expected
output) → all dispatches in ONE response (= parallel) → review, check
conflicts, run full suite, spot-check. Not lifted (native Agent tool +
judgment suffices).

### 14. `writing-skills` — 679 lines (+ 3 major references)
The meta-skill. "Writing skills IS TDD applied to process documentation."
"If you didn't watch an agent fail without the skill, you don't know if the
skill teaches the right thing."
- **Iron Law**: `NO SKILL WITHOUT A FAILING TEST FIRST` (applies to edits
  too).
- Skill Discovery Optimization: description = when-to-use, NEVER the process
  (a process-summarizing description measurably caused agents to skip steps
  — one review instead of two); keyword-rich; verb-first gerund names; token
  targets (<150 words always-loaded, <200 frequent, <500 other); never
  `@file` links (force-load).
- **Match the Form to the Failure** (measured doctrine): discipline failure
  → prohibition + rationalization table + red flags; wrong-shaped output →
  positive recipe (prohibition arm measurably WORSE than no guidance);
  omitted element → required template slot; conditional behavior →
  observable predicate. "No nuance clauses" (one nuance clause degraded a
  winning recipe); "exemption clauses don't scope."
- Testing: pressure scenarios (combine 3+ pressures: time/sunk-cost/
  authority/economic/exhaustion/social); no-guidance control required; 5+
  reps; variance is a metric; meta-testing ("how could the skill have been
  written so Option A was the only answer?").
- persuasion-principles.md: Cialdini applied; Meincke et al. 2025 (N=28k,
  compliance 33%→72%): Authority (imperatives), Commitment (announcements,
  todos), Scarcity, Social Proof, Unity; AVOID Reciprocity; NEVER Liking
  (sycophancy). Ethical test: "Would this serve the user's genuine interests
  if they fully understood it?"

---

## (b) Skill dependency graph

Golden path: `using-superpowers` → `brainstorming` → `writing-plans` →
(`subagent-driven-development` | `executing-plans`) →
`finishing-a-development-branch`. Each hop enforced by `**REQUIRED
SUB-SKILL:**` markers or terminal-state locks; the plan document carries the
marker so a fresh session re-enters the chain.

Debugging path: `systematic-debugging` → `test-driven-development` →
`verification-before-completion` (one-directional; discipline skills are
leaves).

Meta path: `writing-skills` → `test-driven-development`.

Islands: `receiving-code-review`, `dispatching-parallel-agents`.

---

## (c) Enforcement techniques catalog (16)

1. **Pseudo-XML severity tags** — `<EXTREMELY-IMPORTANT>`, `<HARD-GATE>`,
   `<SUBAGENT-STOP>`; exactly three in the corpus, one use each (scarcity is
   the point).
2. **Iron Law** — short ALL-CAPS absolute in a fenced code block + one-line
   consequence. Four instances repo-wide.
3. **Spirit-vs-letter clamp** — one sentence killing "I'm honoring the
   intent" arguments; documented as the change that made TDD bulletproof.
4. **Rationalization tables** (| Excuse | Reality |) + **red-flags lists**
   (verbatim observed thought-strings → uniform imperative). Rule: every
   entry from an OBSERVED baseline failure, never invented.
5. **Loophole-closure lists** ("No exceptions:" + the specific workarounds).
6. **Announce-usage requirement** (commitment principle).
7. **Todo-forcing** ("checklists without todo tracking = steps get skipped.
   Every time").
8. **Phrase-level tripwires** — self-checks keyed on concrete tokens the
   model would emit ("do not flag", "Thanks", "Great!").
9. **Positive recipes** for output shape (prohibitions measurably backfire
   there).
10. **Structural gates** — phase gating, terminal-state locks, counter-based
    breakers (3-fix, 5-round), REQUIRED template slots, file-based state
    that survives compaction (ledger).
11. **Human-decision quarantine** — exact-string confirmations (typed
    `discard`), verbatim menus.
12. **Borrowed authority** — rules attributed to "your human partner";
    the user's frustrated phrasings as triggers.
13. **Cost anchoring with real numbers** — "42k chars, 99% pasted history";
    "94% PR rejection rate".
14. **Deliberate redundancy** — key mandates appear 3-4× in different
    contexts.
15. **Consent/escalation affordances** — "It is always OK to stop and say
    'this is too hard for me.' Bad work is worse than no work."
16. **Anti-sycophancy** — Liking principle banned; gratitude banned in
    review contexts.

---

## (d) Hook mechanics

`hooks/hooks.json`: single SessionStart hook, `matcher:
"startup|clear|compact"` (re-injects after /clear AND compaction — this is
what makes the bootstrap survive long sessions), `shell: "bash"` (Windows
Git-Bash dispatch), `async: false` (session blocks until context injected).
Claude Code auto-discovers `skills/` and `hooks/hooks.json`; plugin.json
declares neither.

`hooks/session-start` (49-line bash): cats the full using-superpowers
SKILL.md (frontmatter included), escapes for JSON via 5 bash parameter
substitutions, wraps in `<EXTREMELY_IMPORTANT>You have superpowers…`, then
three-way platform branch: CURSOR_PLUGIN_ROOT → `{"additional_context"}`;
CLAUDE_PLUGIN_ROOT && !COPILOT_CLI →
`{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext"}}`;
else `{"additionalContext"}`. Emits via printf (bash 5.3 heredoc hang
workaround). Claude Code reads BOTH context fields without dedup — emit only
one. Nothing else is injected: no skill index, no project state.

`run-hook.cmd`: polyglot batch/bash file (valid as both); Windows probes
Git-Bash paths and **exits 0 silently if no bash** — never break the
session. Hook scripts are extensionless (avoids Windows `.sh`
auto-detection).

Other bootstrap shapes (for reference): opencode/pi = in-process injection
as user-role message with dedup guard; Gemini = `GEMINI.md` with two
`@`-includes; Codex plugin declares an empty `hooks` object to suppress
auto-discovery.

---

## (e) Root instruction files

- `AGENTS.md` is a **symlink to CLAUDE.md**. Both are contributor rules, not
  injected: "94% PR rejection rate" framing; 6 MUSTs before any PR;
  "Skills are not prose — they are code that shapes agent behavior";
  skill changes require eval evidence; "'your human partner' is deliberate,
  not interchangeable with 'the user'."
- `GEMINI.md` (2 lines) is a *bootstrap*, not contributor rules —
  asymmetric purpose despite sitting alongside.

---

## (f) Format conventions

- Frontmatter: `name` + `description` only. Description: "Use when…",
  third-person, trigger-only, keyword-rich, symptoms included ("before
  writing implementation code"); may append an obligation clause after a
  dash ("…; evidence before assertions always").
- Body: Title → Overview (core principle 1-2 sentences) → When to Use →
  Core Pattern → Quick Reference → Implementation → Common Mistakes.
  Discipline skills add: Iron Law, spirit-vs-letter, rationalization table,
  red flags, checklist.
- Emphasis ladder (descending): pseudo-XML tags → fenced Iron Laws →
  `**Bold:**` labeled directives → ALL-CAPS inline → ✅/❌ pairs → tables.
- Graphviz DSL: diamond=question, box=action, octagon-red=STOP,
  doublecircle=entry/exit; labels are semantic sentences.
- Cross-refs: `**REQUIRED SUB-SKILL:**` / `**REQUIRED BACKGROUND:**`;
  namespaced `superpowers:<name>`; conditional loads phrased as predicates;
  never `@file`.
- Platform neutrality: skills name ACTIONS never tools ("dispatch a
  subagent", "your file-creation tool"); tool names live in
  `references/<harness>-tools.md` only.
- Voice: always "your human partner", never "the user" (tested, deliberate).

---

## (g) Testing approach

- `tests/` = non-LLM plumbing (hook JSON shape per platform under `env -i`;
  script unit tests; per-harness wiring).
- `evals/` = behavioral (separate repo `superpowers-evals`, "drill": real
  tmux sessions, LLM actor + LLM verifier; NOT in this repo).
- `tests/explicit-skill-requests/`: does Claude invoke a named skill; also
  asserts no non-Skill tool use BEFORE the skill invocation (premature-action
  detection); adversarial prompt corpus (skip-formalities, action-oriented…).
- `test-worktree-native-preference.sh`: an actual RED-GREEN-PRESSURE skill
  test in bash (skill with section removed → agent misbehaves; real skill →
  correct; pressure variant).
- In-skill artifacts: pressure-test scenario files + CREATION-LOG kept as
  worked examples of the methodology.

## Docs worth reading in full when improving chimera

- `docs/porting-to-a-new-harness.md` (828 lines) — 3-component architecture,
  two invariants, capability checklist, porter gotchas.
- `docs/superpowers/specs/2026-06-10-positive-instruction-redesign-design.md`
  — measured doctrine: tripwires work, recognition tables work,
  composition-prohibitions backfire, ties go to shorter phrasing.
- `docs/superpowers/specs/2026-06-10-strict-cost-sdd-design.md` — SDD cost
  model (~$13/run) and "Cheapen mechanics, never judgment."
