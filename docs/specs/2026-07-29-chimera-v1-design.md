# Chimera v1.0 — Complete Design Spec

Status: DRAFT — pending Leo's review.
Inputs: [workflow inventory](2026-07-29-workflow-inventory.md) (locked) +
three deep-mining reports over `~/personal_projects/superpowers` (v6.2.0)
and `~/personal_projects/ECC` (v2.1.0), preserved in full at:
- [docs/research/2026-07-29-superpowers-deep-dive.md](../research/2026-07-29-superpowers-deep-dive.md)
- [docs/research/2026-07-29-ecc-learning-hooks.md](../research/2026-07-29-ecc-learning-hooks.md)
- [docs/research/2026-07-29-ecc-loop-commands-guides.md](../research/2026-07-29-ecc-loop-commands-guides.md)

Consult those before re-reading either reference repo — they contain the
per-skill dossiers, enforcement-technique catalog, hook mechanics, format
conventions, and adopt/skip verdicts this spec builds on.

Chimera v1.0 is a **self-contained** personal harness: a Claude Code plugin
(skills + commands + one agent + hooks) plus CLAUDE.md and genesis document
templates. The skills it needs are lifted in and adapted from the reference
repos, so no other workflow plugins are required — running chimera alone
keeps the context window lean. claude-mem remains an optional external
dependency (memory is delegated, not rebuilt).

---

## 1. Design principles

1. **Least machinery.** Escalate only as needed: CLAUDE.md line < skill <
   command < hook. Hooks only where instructions demonstrably fail.
2. **Traceability.** Every artifact maps to a workflow (W1–W9). Nothing ships
   without a named failure mode it prevents.
3. **One loop, two vocabularies.** Mode (build | exploration) is set at W1 and
   shades every stage. No parallel harness for analysis work.
4. **Match the form to the failure** (superpowers' measured doctrine):
   discipline failures get Iron Laws + rationalization tables + red flags;
   wrong-shaped output gets positive recipes; omissions get required template
   slots. Never pile persuasion onto reference material.
5. **Token discipline.** The injected bootstrap stays under ~70 lines. Skills
   load on demand. Descriptions state *when to use*, never the process
   (process-summarizing descriptions measurably cause step-skipping).
6. **Evidence over claims.** Verification runs commands; reviews cite
   file:line; findings state a concrete failure scenario.

### Enforcement tiers (from the ECC TDD analysis)

| Tier | Mechanism | Chimera v1.0 uses it for |
|---|---|---|
| Suggestive | instructions in context | all skill content; branch nudge (warn-only) |
| Procedural | required artifacts, gates, announce/todo forcing | plan docs, findings docs, review verdicts, typed `discard`, /start-task Phase 0 branch gate |
| Enforced | deterministic hooks | bootstrap injection only |

**Enforcement posture (Leo, 2026-07-29): hard gates live inside the feature
loop; outside the loop, at most a quiet nudge.** Chimera never blocks work
the user does directly on main (docs, chores, quick fixes). Discipline is
opt-in by entering the loop — and strict once inside it.

Finding: **neither reference enforces TDD at tier 3** — superpowers' rigor is
tier 1–2 text hardened by adversarial testing plus the tier-3 *bootstrap*
(session-start injection making skills fire). v1.0 matches that. A RED-gate
PreToolUse hook (block edits to non-test source files without an observed
failing test) is the flagship **v1.1 candidate** — deferred because it needs
session-state machinery and dogfooding should confirm the text alone leaks.

---

## 2. Repository layout

```
chimera/
├── .claude-plugin/plugin.json        # v1.0.0, no plugin dependencies
├── hooks/
│   ├── hooks.json                    # SessionStart + PreToolUse
│   ├── session-start                 # bash; injects using-chimera bootstrap
│   └── branch-nudge.py               # warn-only nudge (never blocks)
├── skills/
│   ├── using-chimera/SKILL.md            # bootstrap/router (injected)
│   ├── designing-features/SKILL.md       # W2
│   ├── writing-plans/SKILL.md            # W3
│   ├── test-driven-development/SKILL.md  # W4 build
│   ├── exploring-reproducibly/SKILL.md   # W4 exploration
│   ├── verifying-before-done/SKILL.md    # W5
│   ├── finishing-a-branch/SKILL.md       # W6+W7
│   └── debugging-systematically/SKILL.md # W8
├── commands/
│   ├── design-project.md             # W10 project genesis
│   ├── start-task.md                 # W1: one trip through the loop
│   └── new-project.md                # W9 bootstrap/scaffold
├── agents/
│   └── code-reviewer.md              # W6 (read-only tools)
├── templates/
│   ├── CLAUDE.user.md
│   ├── CLAUDE.project.md
│   ├── prd-app.md                    # genesis: application PRD
│   ├── prd-ml.md                     # genesis: ML/data PRD (CRISP-DM 1–2)
│   └── system-design.md              # genesis: module table + data flow
├── docs/  (adr/, specs/, testing/smoke.md, update-procedure.md)
├── README.md / CHANGELOG.md / LICENSE
```

8 skills, 3 commands, 1 agent, 2 hook events, 5 templates. (superpowers: 14
skills; ECC: 281/94/67 — we are deliberately below both.)

**Terminology.** A **task** is any loop-sized unit of work — an app feature,
a data pipeline, an EDA pass, a model experiment, a refactor, a spike. The
mode question at kickoff classifies it; "task" carries no software-only
connotation — hence the command name `/start-task`.

**Format conventions** (adopted from the references):
- Skills: frontmatter `name` + `description` only; description third-person
  "Use when…", trigger-only, keyword-rich; body ≤ ~200 lines; `## When to
  Use`, mode variants as short subsections.
- Command files: `description` + `argument-hint`; `$ARGUMENTS`; numbered
  phases; explicit early-exit strings.
- Agent: uniform frontmatter `name/description/tools/model`; **tools are the
  enforcement** — the reviewer gets Read/Grep/Glob/Bash, never Write/Edit.

---

## 3. Hooks

### 3.1 SessionStart — bootstrap injection (the backbone)

Port superpowers' mechanism: `matcher: "startup|clear|compact"` (survives
`/clear` and compaction), `async: false`, bash script that emits
`hookSpecificOutput.additionalContext` containing the full
`using-chimera/SKILL.md` wrapped in an emphasis tag. Claude-Code-only for
v1.0 (no polyglot/multi-harness shims).

### 3.2 PreToolUse — branch nudge (warn-only)

Decision (Leo, 2026-07-29): no ambient blocking. A hook that blocks everyday
edits on main (docs, chores, config) is more enforcement than wanted.
Branch discipline is **loop-scoped**: the hard gate lives in `/start-task`
Phase 0 and in skill text ("never start implementation on main without
consent") — the same tier superpowers uses, where it demonstrably holds.

The hook is a **warn-only nudge**: matcher `Write|Edit|NotebookEdit`;
on main/master, for non-doc source files only, emit a one-line reminder
("editing source on main — for task work, /start-task will branch
first") and **always exit 0**. Doc/chore paths (`*.md`, `docs/**`, and
CHANGELOG/README/LICENSE/gitignore-class basenames) produce no output at
all. `CHIMERA_SILENCE_NUDGE=1` disables it entirely; no blocking-escape
variable exists because nothing blocks. The hook resolves the **edited
file's** git context, not the CWD's, in python3, as a versioned script
file.

No Stop hooks. No PostToolUse. (Formatting/linting belong to per-project
tooling, not the harness.)

---

## 4. Skills — full definitions

### 4.1 `using-chimera` (bootstrap; ≤70 lines — injected every session)

Contents, in order:
1. The Rule: invoke a relevant chimera skill BEFORE any response or action;
   the 1%-chance clause; "announce `Using [skill] to [purpose]`; if it has a
   checklist, create a todo per item."
2. Subagent guard (`ignore this if dispatched as a subagent`).
3. Routing table (the trigger map):
   - "build/add/change X" → `/start-task` (or `designing-features` if
     already on a branch)
   - bug/test failure/unexpected behavior → `debugging-systematically`
   - about to claim done/fixed/passing → `verifying-before-done`
   - implementation work, before writing code → mode check: build →
     `test-driven-development`; exploration → `exploring-reproducibly`
   - work complete, deciding integration → `finishing-a-branch`
4. Compressed red-flags table (~6 rows, the highest-yield rationalizations
   from superpowers' 12).
5. Precedence: user instructions > skills > defaults.

### 4.2 `designing-features` (W2)

Adapted from superpowers `brainstorming`, slimmed to feature altitude, made
mode-aware. Keeps: HARD-GATE (no implementation until design approved),
questions one at a time, 2–3 approaches with recommendation, "too simple to
need a design" anti-pattern, YAGNI, spec self-review (placeholders /
consistency / scope / ambiguity), user review gate, terminal-state lock
(→ `writing-plans` only). Drops: visual companion, project-genesis scoping,
graphviz. Adds:
- **Mode fork.** Build → feature spec (behavior, interfaces, edge cases,
  within existing architecture). Exploration → **research brief**: question,
  hypothesis, data needed, method, and *what result would change what
  decision* (mandatory slot — prevents the aimless notebook).
- Output: `docs/specs/YYYY-MM-DD-<topic>.md`, committed.

### 4.3 `writing-plans` (W3)

Adapted from superpowers `writing-plans` + ECC `/plan`'s best idea. Keeps:
zero-context-engineer framing, bite-sized tasks with exact files/steps, no
placeholders (banned-token list), Global Constraints section, self-review,
plan header carrying its own re-entry instructions. Adds:
- **Pattern Grounding** (ECC): before writing the plan, find one existing
  example per category (naming, error handling, tests) with `file:line`;
  "if no similar code exists, state that explicitly — do not invent a
  pattern."
- **Mode fork.** Build → implementation plan, every task carries its test.
  Exploration → **experiment plan**: data prep → baseline → experiments →
  evaluation metric → **stopping rule** (mandatory slot: "if lift < X after
  N experiments, conclude no-signal and stop").
- Location: `plans/` (gitignored) or `task_plan.md` — plan files are working
  state, not repo artifacts. Specs and findings are committed; plans are not.
- Drops: subagent-driven execution handoff (out of scope), executing-plans
  as a separate skill (execution guidance folded into /start-task).

### 4.4 `test-driven-development` (W4 build)

Lift superpowers' skill **near-verbatim** — it is the most adversarially
hardened artifact in either repo (6 RED-GREEN-REFACTOR iterations, 10+
observed rationalizations closed). Keeps: Iron Law (`NO PRODUCTION CODE
WITHOUT A FAILING TEST FIRST`), spirit-vs-letter clamp, delete-means-delete
loophole closure, verify-RED and verify-GREEN gates, rationalization table,
red-flags list, checklist, human-gated exceptions. Adds two chimera sections:
- **Deterministic boundary** (ML): TDD covers transforms, shapes, schemas,
  leakage checks; model quality is evaluation metrics → exploration-mode
  findings, never faked as unit tests.
- **Promotion rule**: promoting a winning experiment is a new build-mode
  feature; experiment code is reference only; the experiment's numbers on the
  pinned snapshot are the acceptance criteria.

### 4.5 `exploring-reproducibly` (W4 exploration) — the one skill written from scratch

No equivalent exists in either reference. Discipline for analysis/spike work:
1. **Brief first**: the research brief from `designing-features` exists and
   names the decision at stake (tripwire: "opening a notebook without a
   brief → stop, write the brief").
2. **Pin everything**: data snapshot (path + hash or immutable query), random
   seeds, environment. A result that can't be re-run is not a result.
3. **Log as you go**: findings file (`docs/findings/YYYY-MM-DD-<topic>.md`,
   committed) records assumption → experiment → number → interpretation at
   the time of observation, not reconstructed later.
4. **Honor the stopping rule** from the experiment plan; extending the search
   requires updating the plan first (prevents endless fishing).
5. **End with a decision**: the findings doc closes with "decision:
   <adopt/reject/park> because <numbers>". The recorded decision is the
   deliverable.
6. Exit paths: promotion rule (→ new build-mode task) or archive.
7. **Notebook conventions** (Leo's standing preference, encoded once here
   instead of per-project): EDA/analysis notebooks live in `notebooks/`,
   named `NN-topic.ipynb`, structured objective → data loading (pinned
   snapshot stated) → analysis → findings-summary cell mirroring the entry
   in the findings doc. Project-specific data locations stay in that
   project's CLAUDE.md.
Verification variant: clean rerun reproduces the reported numbers.

### 4.6 `verifying-before-done` (W5)

Lift superpowers `verification-before-completion` near-verbatim: Iron Law
(`NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE`), the 5-step gate
function (identify → run → read → verify → claim), claims-vs-evidence table,
anti-paraphrase clause, "Great!/Perfect!/Done!" tripwire. Add one row for
exploration mode: claim "the analysis shows X" requires a clean rerun
matching the reported numbers.

### 4.7 `finishing-a-branch` (W6 + W7)

Superpowers `finishing-a-development-branch` + the review gate folded in as
Step 0 (one skill, since review-then-finish is always one motion for a solo
dev):
- **Step 0 — review gate.** Dispatch the `code-reviewer` agent once on
  `BASE..HEAD` (build mode) or run the methodology pass on the findings doc
  (exploration mode: leakage, look-ahead bias, train/test hygiene,
  numbers-match-code). Act by severity; push back on wrong findings with
  evidence; one pass only — no Stop-hook re-review (duplicate reviews burn
  tokens without adding signal).
- Steps 1–6 from superpowers: green suite first; verbatim 3-option menu
  (merge locally / push + PR / keep as-is); base-branch confirmation; merge
  path re-runs tests on the merged result; cleanup only of self-created
  worktrees; **typed `discard`** quarantine for destruction; the 9-row
  rationalization table guarding the human decision point.
- Chimera adjustments: PR path applies Leo's preferences (conventional-commit
  title, no boilerplate footers, no co-author); exploration mode ends with
  findings-doc commit + decision, experiment code archived, not merged.

### 4.8 `debugging-systematically` (W8)

Lift superpowers `systematic-debugging` core: Iron Law (`NO FIXES WITHOUT
ROOT CAUSE INVESTIGATION FIRST`), four phase-gated phases, single-hypothesis
rule, **3-fix breaker** ("Fix #3 didn't work → question the architecture, do
not attempt Fix #4"), red flags, "signals from your human partner" section,
Phase 4 chaining to TDD (failing test first) and verification. Drop the three
deep-reference files for v1.0 (root-cause-tracing etc.) — add back if
dogfooding wants them.

**Deliberately not lifted from superpowers:** subagent-driven-development
(503-line orchestration machine — not a solo bare-minimum workflow),
executing-plans, dispatching-parallel-agents (native Agent tool suffices),
using-git-worktrees as a standalone skill (worktree offer folded into
/start-task Step 0), receiving-code-review (its no-sycophancy core
becomes ~3 lines in the review gate), writing-skills (use the installed
skill-creator when authoring; revisit at v1.x for /learn).

---

## 5. Commands

### 5.1 `/design-project` (W10 — project genesis; added 2026-07-29)

Added after Leo's workflow walkthrough showed project genesis (brainstorm →
PRD → architecture → system design) is a repeated workflow, and that system
design — modules with expected inputs/outputs — was missing even from his
pre-chimera process. One flow, type-aware in Phases 1, 2, and 4; the project
type (application | ML/data | hybrid) is asked up front.

```
Phase 1 — DISCOVER       brainstorm the idea, then PRD from the type-matched
                         template (approval gate):
                         App: prd-app.md — problem, audience, solution,
                              success measures
                         ML:  prd-ml.md — CRISP-DM phases 1–2: business
                              understanding (objectives, business success
                              criteria, proxy ML metric, baseline to beat) +
                              data understanding (sources, access, quality,
                              initial EDA questions) + constraints (latency,
                              interpretability, cost)
                         Hybrid: both, merged at Phase 3.
Phase 2 — ARCHITECTURE   tradeoff discussion → decisions recorded in ADR(s).
                         App: stack, boundaries, integrations.
                         ML:  data stack, pipeline orchestration, batch vs
                              streaming, serving, experiment tracking, data
                              versioning — plus modeling CONSTRAINTS only.
Phase 3 — SYSTEM DESIGN  docs/system-design.md: module table —
                         module | responsibility | inputs | outputs | deps —
                         plus data flow. (Patches CRISP-DM's missing
                         engineering phase.)
Phase 4 — ROADMAP        docs/roadmap.md: the initial backlog as a table of
                         loop tasks — # | task | mode | depends on.
Phase 5 — SCAFFOLD       hand off to /new-project (skipped if repo exists).
```

**The genesis-vs-loop decision rule** (stated in the command): *if an
experiment could settle it, don't settle it by argument — record it as a
constraint and send the choice into the loop as an exploration task. If
changing it later means rewriting infrastructure, settle it at genesis.*
Model-family selection is the canonical loop-side decision; pipeline
orchestration is the canonical genesis-side one.

**CRISP-DM compilation** (how ML methodology executes through the loop —
full methodology honored, no second harness):

| CRISP-DM phase | Chimera realization |
|---|---|
| 1 Business Understanding | prd-ml.md (Phase 1) |
| 2 Data Understanding | prd-ml.md (Phase 1) + early exploration tasks |
| 3 Data Preparation | build-mode tasks (pipelines, TDD) |
| 4 Modeling | exploration-mode tasks (experiments, pinned data, stopping rules from PRD metrics) |
| 5 Evaluation | metrics/baselines inherited from prd-ml.md into every experiment plan |
| 6 Deployment | build-mode tasks via the promotion rule |
| back-arrows | new exploration tasks — the loop iterates naturally |

**Roadmap semantics:** a queue, not a plan — rows carry no specs or task
breakdowns; each row later gets its own `/start-task` run with full
discipline. Reorderable; outcomes insert/remove rows. It is the project's
persistent "what's next" state (a fresh session opens the roadmap instead of
re-deriving priorities) — a markdown table doing the job of a dedicated
backlog CLI at ~2% of the machinery. App-project roadmaps derive from
system-design modules in dependency order; ML roadmaps compile from
CRISP-DM 3–6.

All genesis artifacts (PRD, ADRs, system design, roadmap) are committed.

### 5.2 `/start-task` (W1) — rewritten

```
Phase 0 — GATE      not on main/master (else offer branch or worktree;
                    honor branch-guard escape rules). ECC branch decision
                    table: on main + dirty → STOP, ask stash-or-commit.
Phase 1 — MODE      "Is this producing code we'll keep, or an answer we'll
                    act on?" → build | exploration. Default from project
                    CLAUDE.md; feature answer overrides. Record in plan file.
Phase 2 — DESIGN    invoke designing-features → committed spec/brief.
                    Where genesis docs exist: the task comes from
                    docs/roadmap.md, and the spec names which system-design
                    module(s) it touches and writes against their I/O
                    contracts. Finish updates the roadmap row.
Phase 3 — PLAN      invoke writing-plans → plan file with tests or
                    experiments + stopping rule.
Phase 4 — EXECUTE   work the plan inline. Build → test-driven-development.
                    Exploration → exploring-reproducibly. 3-attempt circuit
                    breaker on any repeated failure (ECC): same error after
                    3 fixes, or a fix that adds more errors than it removes
                    → stop and ask.
Phase 5 — VERIFY    invoke verifying-before-done.
Phase 6 — FINISH    invoke finishing-a-branch (includes review gate).
```
Steps announce, create todos, and are resumable: re-invoking `/start-task`
with an existing plan file resumes at the first unchecked task (plan file +
git log are the source of truth, not conversation memory).

### 5.3 `/new-project` (W9) — new, thin

1. Preconditions: refuse to overwrite an existing CLAUDE.md without showing a
   diff (ECC rule).
2. `git init` if needed; `.gitignore` gets `plans/` + stack defaults.
3. Copy `templates/CLAUDE.project.md`; fill: one-paragraph brief (asked),
   default mode (asked), detected commands (build/test/lint/run — only what's
   actually detected, ECC project-init rule: never invent).
4. Optional: `docs/` skeleton (`specs/`, `findings/`, `adr/`).
5. Explicitly does NOT: generate PRDs, pick architecture, install deps.

---

## 6. Agent: `code-reviewer`

One agent, built from ECC's `code-reviewer` (the best file in that repo)
merged with superpowers' reviewer template. Frontmatter: `tools: Read, Grep,
Glob, Bash` (structurally cannot edit), `model: inherit` for v1.0 (opus/sonnet
routing is a v1.x cost optimization).

Keeps from ECC: >80% confidence filter; the four-question pre-report gate
(exact line? concrete failure mode? read surrounding context? severity
defensible?); HIGH/CRITICAL require proof (snippet + scenario + why existing
guards miss it); **"zero findings is a valid review — do not manufacture
findings"**; the false-positive skip list (trimmed to ~8 entries, Python/data
entries added, React-specifics dropped); consolidation rule; "would a senior
engineer actually change this?" heuristic; severity matrix →
approve / approve-with-comments / request-changes / block.
Keeps from superpowers: read-only-review clause; strengths-before-issues;
explicit verdict required ("don't avoid a clear verdict"); calibration
("not everything is Critical").
Adds: exploration-mode rubric (methodology pass: leakage, look-ahead bias,
snapshot pinning, numbers-match-code) selected by the dispatch prompt.
Drops: ECC's Prompt Defense Baseline boilerplate; stack-specific checklists.

---

## 7. Templates

### 7.1 `templates/CLAUDE.user.md` (~30 lines, index style)

Rebuilt from the live `~/.claude/CLAUDE.md`, deliberately:
- Git: Conventional Commits `type(scope): summary`; no co-author lines; no
  boilerplate footers in PR bodies; subagents never commit — main agent
  commits after review.
- New projects: `plans/` in `.gitignore`.
- Docs lookup: context7 for unfamiliar-library work.
- Frontend: invoke frontend-design + ui-ux-pro-max before UI code.
- Pointer: chimera plugin owns the dev loop; project specifics live in each
  project's CLAUDE.md.
(Nothing that chimera skills already encode — no duplicated TDD/verification
prose; the file stays a preferences index, per ECC's router insight.)

### 7.2 `templates/CLAUDE.project.md` (~40 lines with placeholders)

```markdown
# <project>
<one-paragraph brief — what this is, for whom>

## Mode
Default: build | exploration   (features may override at /start-task)

## Commands
build: … / test: … / lint: … / run: …        (only verified commands)

## Architecture
<5–10 line map; links to docs/specs, ADRs, PRD if they exist>

## Conventions
<the 3–5 that differ from defaults; link rules docs rather than inline>

## Gotchas
<known traps: env quirks, data locations, slow tests>
```
Per ECC's minimal-CLAUDE.md finding: commands and repo-specific notes are the
load-bearing content; everything else is optional and short. It loads every
session — brevity is a feature. The Architecture section links to the genesis
docs (PRD, system design, roadmap) when they exist rather than inlining them.

### 7.3 Genesis document templates

- **`templates/prd-app.md`** — Problem statement · Target audience · Solution
  (what it is, how it solves the problem) · Success measures · Non-goals.
- **`templates/prd-ml.md`** — Business understanding (objectives; business
  success criteria; the offline ML metric that proxies them; baseline to
  beat) · Data understanding (sources, access, quality expectations, initial
  EDA questions) · Constraints (latency, interpretability, compute/cost,
  candidate approaches worth trying) · Non-goals. CRISP-DM phases 1–2 in
  template form.
- **`templates/system-design.md`** — Module table (module | responsibility |
  inputs | outputs | depends on) · Data flow sketch · Repo layout (where
  notebooks vs pipeline code vs docs live) · Open questions.

Each ≤ 1 page of prompts; filled during `/design-project` Phases 1 and 3.
The roadmap needs no template (its 4-column table is defined in the
command).

---

## 8. Install / update story

- Install: `/plugin marketplace add Leo-QJ-Justin/chimera` +
  `/plugin install chimera@chimera` (unchanged).
- **Update procedure** (`docs/update-procedure.md`): the exact steps through
  the three staleness layers (GitHub → marketplace mirror → install cache →
  live session), so an update is one documented sequence instead of
  archaeology.
- Keep enabled plugins minimal: chimera is self-contained, so other workflow
  plugins can stay disabled (ECC guide: fewer enabled plugins = healthier
  context window).

## 9. Testing

- `docs/testing/smoke.md` updated for v1.0: hook-output shape check for
  session-start (assert the JSON envelope, superpowers-style), branch-guard
  matrix (main/branch × allowlisted/code paths × escape var), one manual
  end-to-end `/start-task` run per mode.
- Skill behavior evals (pressure-testing per superpowers `writing-skills`)
  are explicitly v1.x — but any *edit* to a lifted discipline skill must
  preserve its Iron Law / rationalization-table structure.

## 10. Out of scope for v1.0 (named)

RED-gate TDD hook (v1.1 flagship candidate) · `/learn` retro (v1.x, modeled
on ECC `/learn-eval`'s Save/Improve/Absorb/Drop quality gate, manual not
automated) · language rules packs (v2) · multi-harness ports · model
routing · SDD-style subagent orchestration · session-summary hooks
(claude-mem's job). (`/design-project` was originally deferred here; moved
into v1.0 on 2026-07-29 after Leo's workflow walkthrough evidenced project
genesis as a repeated workflow — see §5.1.)

## 11. Build order (Phase 3 plan outline)

1. Repo structure + plugin.json v1.0.0.
2. Hooks (session-start + extracted branch guard with file-context fix) +
   smoke tests — the enforcement backbone ships first.
3. Skills: lift-and-adapt in dependency order: using-chimera →
   verifying-before-done → test-driven-development → debugging-systematically
   → designing-features → writing-plans → exploring-reproducibly →
   finishing-a-branch.
4. Agent: code-reviewer.
5. Commands: /start-task, /new-project, /design-project.
6. Templates (CLAUDE.md ×2 + genesis ×3) + README + CHANGELOG +
   update-procedure.
7. Install locally, keep other workflow plugins disabled, dogfood one real task per
   mode (Phase 4).
