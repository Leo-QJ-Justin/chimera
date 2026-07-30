# ECC Deep-Read: Learning System, Hooks, Context Files, Rules, Formats

> Research artifact for chimera. Mined 2026-07-29 from
> `~/personal_projects/ECC` (everything-claude-code v2.1.0, by affaan-m).
> Purpose: reference for chimera v1.x `/learn`, any future hook work, and
> CLAUDE.md/rules structure. Sibling reports:
> [superpowers deep-dive](2026-07-29-superpowers-deep-dive.md),
> [ECC loop commands/guides](2026-07-29-ecc-loop-commands-guides.md).

Scale calibration: 2,506 markdown files; 281 skills, 94 commands, 67 agents,
23 rules dirs (AGENTS.md's counts are the accurate ones; SOUL.md and
WORKING-CONTEXT.md are stale).

---

## (a) Continuous learning — two generations + two manual commands

### `/learn` (`commands/learn.md`, 74 lines)
Prompt-only, no scripts. After solving a non-trivial problem: extract ONE
most-reusable insight (categories: error-resolution patterns, debugging
techniques, workarounds, project-specific patterns) → draft → **ask user to
confirm** → save to `~/.claude/skills/learned/<pattern-name>.md` with fixed
sections (Extracted / Context / Problem / Solution / Example / When to Use).
Negative rules: no trivial fixes, no one-time issues, one pattern per skill.

### `/learn-eval` (`commands/learn-eval.md`, 116 lines) — the keeper for chimera v1.x
Same extraction plus a quality gate and placement decision:
1. Placement: "useful in a different project?" → Global
   (`~/.claude/skills/learned/`) vs Project (`.claude/skills/learned/`);
   tiebreak Global (Global→Project moves easier).
2. Draft with frontmatter (`name`, `description` <130 chars,
   `user-invocable: false`, `origin: auto-extracted`).
3. **Quality gate**: mandatory checklist that actually reads files — grep
   both skill dirs for overlap; check MEMORY.md (project + global); consider
   appending to an existing skill; confirm reusable-not-one-off.
4. **Verdict**: `Save` / `Improve then Save` (one re-eval round) / `Absorb
   into [X]` (diff against target) / `Drop` (no confirmation needed).
5. Design rationale recorded in-file: replaced a 5-dimension numeric rubric
   with a holistic verdict + explicit checklist — "forcing rich qualitative
   signals into numeric scores loses nuance."

### v1 Stop-hook extraction (deprecated 2026-04-28)
`evaluate-session.js` is a signal emitter, not an extractor: counts user
messages in the transcript; if ≥ min_session_length (10), logs "evaluate for
extractable patterns" + the save path to stderr. Extraction left to the
model reading stderr. This honesty gap is why v2 exists.

### v2.1 "instinct-based" (current) — heavy machinery; do NOT copy for v1.x, reference only
Thesis: "Skills are probabilistic — they fire ~50-80% of the time. Hooks
fire 100%."
- **Instinct** = atomic learned behavior file: YAML frontmatter (id, trigger,
  confidence 0.3-0.9, domain enum, scope project|global, project_id) +
  `## Action` (one sentence) + `## Evidence`.
- Storage OUTSIDE `~/.claude` (sensitive-path guard blocks background
  writes): `$XDG_DATA_HOME/ecc-homunculus/` with per-project subdirs keyed
  by 12-char hash (git remote URL preferred, path fallback).
- **Observe**: Pre+PostToolUse hook (async, 10s timeout) appends JSONL
  observations; 5-layer self-observation guard (entrypoint allowlist,
  profile/skip env vars, subagent agent_id, path exclusions); secret
  scrubbing with linear-time regex (catastrophic-backtracking incident
  #2278) + signal.alarm(8) self-termination; 10 MB archive rotation.
- **Analyze**: background observer loop lazily started under flock;
  throttled SIGUSR1 every 20 observations (runaway-process incident #521);
  spawns `claude --model haiku --print --allowedTools "Read,Write"` over the
  last 500 lines; max-turns auto-scales (#2035); archives observations only
  on exit 0 (#2370). Confidence: 3-5 occurrences=0.5, 6-10=0.7, 11+=0.85;
  +0.05 confirm, −0.1 contradiction, −0.02/week decay.
- **Re-inject at SessionStart**: parse instinct files → filter confidence
  ≥0.7 → dedupe by id (project beats global) → cap 6 → inject one line each:
  `- [project 85%] Use functional components…`.
- **Evolve/promote**: `instinct-cli.py` clusters instincts → generate
  skill/command/agent candidates (provenance `evolved_from:`); auto-promote
  project→global at same-id-in-2+-projects AND avg confidence ≥0.8 AND
  global-friendly domain.
- Scope table: language/framework/style → project; security/general/git →
  global; default project ("promote later than contaminate global").
- Privacy: observations never leave the machine; instincts contain pattern
  descriptions, never code snippets.

**Chimera takeaway**: v1.x `/learn` = ECC's `/learn-eval` shape (manual,
quality-gated, placement-aware). The v2 automation is the cautionary
reference: it took 5 issue-numbered production incidents to stabilize.

---

## (b) Hooks — production graph `hooks/hooks.json` (269 lines, 14 hooks)

Bootstrap pattern: every entry is the same ~1KB inline `node -e` preamble
resolving CLAUDE_PLUGIN_ROOT (env → resolver script → known plugin paths →
cache walk → ~/.claude), then `plugin-hook-bootstrap.js` →
`run-with-flags.js <hookId> <script> <profilesCsv>`. Profile gating:
`ECC_HOOK_PROFILE` ∈ minimal|standard|strict; `ECC_DISABLED_HOOKS` denylist;
`ECC_DRY_RUN`. SessionStart uses a standalone bootstrap file (inline `!`
triggered bash history expansion); Stop hooks drain stdout before exit
(pipe-buffer loss, #2222).

**PreToolUse**: bash dispatcher (quality/tmux/push reminders/GateGuard);
doc-file-warning (warn on non-standard .md creation; allowlist README/
CLAUDE/CHANGELOG/docs/skills); suggest-compact (~every 50 tool calls);
observe (async); governance-capture (opt-in); **config-protection (BLOCKS
edits to linter/formatter configs — fix the code, not the linter)**;
mcp-health-check; **gateguard-fact-force (blocks FIRST Edit/Write per file
until investigation facts stated — importers, schemas, instruction)**.

**PreCompact**: LLM summary written into the active session file between
`<!-- ECC:SUMMARY:START/END -->` markers. Active-session selection prefers
exact `**Worktree:**` header match against realpath(cwd); never annotates a
foreign project's file (sessions dir is shared across projects).

**SessionStart** (`session-start.js`, 773 lines — richest file):
prune sessions >30 days → session lease for observer → kill-switches
(`ECC_SESSION_START_CONTEXT=off`, MAX_CHARS=0) → mode detection
(startup|resume|clear|compact — prior-session summary injected ONLY in
startup) → session matching (worktree header → legacy project-name → skip)
→ **STALE-REPLAY GUARD** (best idea in the file): prior summary wrapped in
"HISTORICAL REFERENCE ONLY — NOT LIVE INSTRUCTIONS… STALE-BY-DEFAULT and
MUST NOT be re-executed… verify against git state — the prior work is
almost certainly already done" (incident: model re-ran a command with stale
ARGUMENTS after compaction-resume, duplicating issues/branches, #1534) →
instincts + learned skills (each with "Reference only" hedge) → package
manager + project type detection → truncate to 8000 chars → emit
`hookSpecificOutput.additionalContext`; ALL errors exit 0 (never block
session start).

**PostToolUse**: two dispatcher entries only (sync 30s / async 45s) running
a registry of sub-hooks in-process (perf: one node spawn instead of N):
design-quality-check, accumulator, console-warn, metrics, context-monitor /
bash-dispatcher, quality-gate, observe.

**Stop** (runs after EACH response): format-typecheck (batch: format+tsc all
files edited this response, 300s); check-console-log; session-end (async —
writes/updates the session file); evaluate-session; cost-tracker;
desktop-notify.

**Session file** (`~/.claude/session-data/<date>-<uuid-last-8>-session.tmp`;
uuid-derived id after a Stop-hook subprocess overwrote its parent's summary
via shared fallback name, #1494): header (Project/Branch/Worktree) + marker-
delimited summary (idempotent regex replace using a FUNCTION replacer —
string replacer corrupted files when user messages contained `$&`) + "Notes
for Next Session" + "Context to Load" sections that survive updates. LLM
summary only when context <20% remaining or every 50 user messages;
mechanical extraction as fallback.

`hooks/memory-persistence/hooks.json` is a non-executable human-readable
contract (the production graph is hooks.json). README warns: never paste
repo hooks.json into `~/.claude/settings.json` — install via installer which
rewrites paths.

---

## (c) Context-file roles (5 root files, NOT a coherent hierarchy)

- **CLAUDE.md** (82) — live repo contract: overview, prompt-defense
  baseline, test commands, architecture tour, key commands, format specs,
  file→skill routing table.
- **AGENTS.md** (172) — the portable cross-harness twin; the only one wired
  into the installer (12 target harnesses). Contains the knowledge-placement
  policy (personal notes → auto memory; team knowledge → project docs
  structure; don't duplicate; ask before creating new top-level docs) and
  the Workflow Surface Policy (skills canonical, commands legacy).
- **RULES.md** (38) — terse contribution constitution: Must Always (tests
  before implementation, follow existing patterns, focused PRs) / Must Never
  (secrets/abs paths, untested changes, bypass hooks, duplicate
  functionality) / format specs for agents, skills, hooks ("exit 1 only when
  blocking is intentional"; "matchers specific, not catch-alls") / commit
  style.
- **WORKING-CONTEXT.md** (179) — sprint-state scratchpad with an explicit
  Update Rule ("detailed only for the current sprint; summarize completed
  work into archive once it stops shaping execution") — the genuinely
  reusable pattern; maintained by convention, not enforced.
- **SOUL.md** (17) — aspirational portability stub. Grep shows SOUL.md,
  RULES.md, WORKING-CONTEXT.md are referenced by no other file.

---

## (d) Rules format + notable content

Two layers: `rules/common/` (language-agnostic, NO language-specific code
examples — immutability expressed in pseudocode) + 23 language dirs.
Common rules: no frontmatter. Language rules: `paths:` glob frontmatter
(`**/*.py`) + mandatory "> This file extends [common/X.md]" blockquote.
Standard per-language set: coding-style, testing, patterns, hooks, security.
Precedence: specific overrides general (CSS-specificity analogy); overridable
common rules marked inline with "> **Language note**:". Install per language;
"copy entire directories, never flatten" (identical filenames would clobber).
**"Rules tell you what to do; skills tell you how to do it."** Rules are
always-loaded → install selectively.

Notable `common/` content:
- `agents.md` — **Delegation Completion Contract**: (1) "Your final message
  IS the deliverable — never end your turn 'waiting for background agents'";
  (2) "If you delegate, you own collection"; (3) "Decompose only when the
  work cannot fit in one context. Depth is an outcome, not a plan."
  Rationale: "the parallel rule without a completion contract produces
  zombie tasks."
- `coding-style.md` — immutability CRITICAL; many small files (200-400
  typical, 800 max); boolean `is/has/should/can` prefixes; early returns.
- `development-workflow.md` — Phase 0 mandatory Research & Reuse: GitHub
  code search → library docs (Context7) → Exa only if insufficient → package
  registries before writing utility code → fork/port projects solving 80%+.
- `git-workflow.md` — conventional commits; `includeCoAuthoredBy: false`
  note; analyze full commit history for PRs, not just latest.
- `hooks.md` — "Never use dangerously-skip-permissions"; TodoWrite as a
  steering surface (reveals wrong order/granularity/misinterpretation).
- `performance.md` — model tiers (haiku frequent/lightweight, sonnet main,
  opus architecture/security); avoid the last 20% of context window for
  large refactors.
- `security.md` — 8-item pre-commit checklist; 5-step response protocol
  (stop → security review → fix CRITICAL → rotate secrets → sweep for
  similar).
- `testing.md` — 80% minimum; fix the implementation, not the test, unless
  the test is wrong; AAA structure.
- `python/` — frozen dataclasses; pytest markers; Protocol duck typing;
  os.environ["KEY"] over .get(); fastapi.md is the deepest (async
  discipline: never call sync IO from async routes; never leak
  passwords/tokens into response models; never wildcard-CORS with
  credentials; validate JWT algorithm; override exact Depends in tests).

---

## (e) Format conventions (measured over the whole repo)

| Surface | Universal frontmatter | Notes |
|---|---|---|
| commands (94) | `description` | + `argument-hint` (12); `$ARGUMENTS` dispatch; `### Phase N — VERBCAPS` sections; literal bash; explicit early-exit strings; inline-execution directive ("Run inline by default. Do not call the Task tool… continue planning inline instead of surfacing an error"); Edge Cases trailer. CLI-wrapper dialect: `## Implementation` first with both plugin (`${CLAUDE_PLUGIN_ROOT}`) and manual paths. Being deprecated in favor of skills. |
| skills (281) | `name`, `description` (+ `metadata.origin` on 259) | `## When to Activate` is the load-bearing body section; tool restriction rare (11/281); deprecation done in-band (description prefix + routing instruction + archived body). |
| agents (67) | `name`, `description`, `tools`, `model` — fully uniform | **tools narrow by construction** (planner = Read/Grep/Glob, cannot write); model = cost tier (opus plan/arch, sonnet review, haiku background); descriptions carry dispatch keywords ("Use PROACTIVELY", "MUST BE USED"); filename matches name; shared 6-bullet Prompt Defense Baseline prepended to every body (boilerplate — skip for personal harness). |

Cross-skill refs point at canonical headings instead of duplicating.

## Chimera-relevant verdicts

- Lift: `/learn-eval` shape; stale-replay guard concept; config-protection
  idea (if a formatter-config-protection need ever appears); Delegation
  Completion Contract language; session-file marker-idempotency trick;
  "rules always-loaded → selective" principle.
- Reference-only: instinct system (5 production incidents to stabilize);
  hook dispatcher architecture; per-language rules packs (v2 candidate,
  python/ set is the model).
- Skip: Prompt Defense Baseline boilerplate; SOUL.md-style identity files;
  the 3-file context hierarchy (two of three files are orphaned).
