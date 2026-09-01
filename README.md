# chimera

Self-contained personal Claude Code harness: a mode-aware development loop
with project-genesis and scaffolding commands. Skills are adapted from
[Superpowers](https://github.com/obra/superpowers) (Jesse Vincent, MIT) and
the review agent from
[Everything Claude Code](https://github.com/affaan-m/everything-claude-code)
(affaan-m, MIT) — cut down to a bare-minimum workflow set and made
mode-aware for mixed software/ML work.

**Posture: strict inside the loop, frictionless outside it.** Chimera never
blocks work done directly on `main` (docs, chores, quick fixes). Discipline
is opt-in by entering the loop — and enforced once inside.

## The model

**Two altitudes:**

- **Genesis** (`/design-project`): brainstorm → data-contact spike
  (corpus profiled before design) → BIND (evidence → commitments) → PRD
  (app-shaped, or ML-shaped via CRISP-DM phases 1-2) → architecture +
  tradeoffs (ADRs) → system design (modules with I/O contracts) →
  roadmap (task backlog).
- **Loop** (`/start-task`): gate → mode → design → plan → execute → verify
  → review → finish. One roadmap row at a time.

The current shape of every flow is the living map at
[docs/process-map.md](docs/process-map.md), updated in the same commit
as any change that alters a flow.

**Two modes**, declared per task ("code we'll keep, or an answer we'll act
on?"):

| Stage | Build mode | Exploration mode |
|---|---|---|
| Design | task spec (module I/O contracts) | research brief (+ "what result changes what decision?") |
| Plan | implementation plan, tests per task | experiment plan + stopping rule |
| Execute | strict TDD | pinned data, seeds, findings log |
| Verify | fresh test run | clean rerun reproduces numbers |
| Review | code review | methodology review (leakage, bias, hygiene) |
| Finish | merge/PR | recorded decision; experiment code archived |

The bridge is the **promotion rule**: a winning experiment becomes a new
build-mode task, written test-first, with the experiment's numbers as
acceptance criteria. Spike code is never merged.

## Contents

- **12 skills** — `using-chimera` (bootstrap, injected each session),
  `designing-tasks`, `writing-plans`, `test-driven-development`,
  `exploring-reproducibly`, `verifying-before-done`,
  `debugging-systematically`, `finishing-a-branch`, `creating-skills`
  (skill authoring with a should-this-exist gate — replaces the external
  skill-creator plugin), `writing-in-ste` (the genesis-document register:
  one meaning per term, active voice, short sentences),
  `writing-comparative-reports` (report contract + profile-to-brief
  recipe for many-instance investigations), `persistent-model-discovery`
  (grain, immutability, corrections, consumers locked into a TRD before
  the PRD)
- **4 commands** — `/design-project`, `/start-task`, `/new-project`,
  `/retrospect` (the learning loop: friction events → quality gate →
  improvement spec)
- **3 agents** — `code-reviewer` (read-only tools; confidence-gated; "zero
  findings is a valid review"; build + exploration rubrics),
  `eda-profiler` (mechanical first-pass dataset profiling, drafted in the
  analysis style contract; judgment calls returned as questions), and
  `corpus-profiler` (its non-tabular sibling: heterogeneous corpora,
  report regenerated from a committed script)
- **2 hooks** — SessionStart bootstrap injection (`startup|clear|compact`);
  warn-only branch nudge on source edits on main (never blocks;
  `CHIMERA_SILENCE_NUDGE=1` to mute)
- **5 templates** — `CLAUDE.user.md`, `CLAUDE.project.md`, `prd-app.md`,
  `prd-ml.md`, `system-design.md` (modules and contracts, plus an AI
  properties section — memory, evaluation, cost — for systems with a
  model component)
- **1 rules pack** — `rules/common/` + `rules/python/`, copied into each
  project by `/new-project` (see [Rules](#rules))

## Rules

`rules/` holds explicit coding rules in ECC's format — short imperative
files that state WHAT to do, where skills state HOW. `common/` is
language-agnostic; `python/` extends it with `paths:` frontmatter.

They travel by copy, not by plugin load, so other harnesses and a plain
`git clone` see the same files. `/new-project` copies them to
`.claude/rules/chimera/` and imports them from the project CLAUDE.md. For
an existing project:

```bash
mkdir -p .claude/rules
cp -r "${CLAUDE_PLUGIN_ROOT}/rules" .claude/rules/chimera
```

Copy whole directories — `common/` and `python/` share filenames, so a
flattened copy loses one.

## Install

```bash
/plugin marketplace add Leo-QJ-Justin/chimera
/plugin install chimera@chimera
```

Copy `templates/CLAUDE.user.md` over `~/.claude/CLAUDE.md` (merge with any
existing preferences). New projects get their CLAUDE.md via `/new-project`.

Updating an installed chimera: see
[docs/update-procedure.md](docs/update-procedure.md).

## Design documents

- [Workflow inventory](docs/specs/2026-07-29-workflow-inventory.md)
  — the bare-minimum workflow set every artifact traces to
- [v1.0 design spec](docs/specs/2026-07-29-chimera-v1-design.md)
  — every artifact defined, with rationale
- [Reference research](docs/research/) — deep-mining reports over
  Superpowers and ECC (consult before re-reading those repos)

## Testing

`bash tests/test-branch-nudge.sh && bash tests/test-session-start.sh` for
the hooks; [docs/testing/smoke.md](docs/testing/smoke.md) for the manual
end-to-end matrix;
[docs/testing/pressure-scenarios/](docs/testing/pressure-scenarios/) for
the per-change failure scenarios skill edits are walked against before
landing.

## Roadmap

- **v1.1** — RED-gate TDD hook (PreToolUse block on source edits without an
  observed failing test; exceeds what either reference enforces)
- **v2** — language rules packs: `common/` + `python/` shipped; further
  languages when a project needs one

## License

MIT
