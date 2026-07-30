# Changelog

All notable changes to chimera are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [SemVer](https://semver.org/).

## [1.1.0] - 2026-07-30

### Added
- `creating-skills` skill — skill authoring synthesized from Anthropic's
  skill-creator, Superpowers' writing-skills, and ECC's learn-eval gate:
  should-this-exist verdict (Create/Absorb/Automate/Drop), format rules,
  match-the-form-to-the-failure doctrine, and a test-before-deploy gate.
  Makes chimera self-sufficient for skill authoring; the external
  skill-creator plugin can be disabled. Routed from the bootstrap
  ("Creating or editing a skill").

## [1.0.0] - 2026-07-29

Initial release. A self-contained personal harness built per the
[v1.0 design spec](docs/specs/2026-07-29-chimera-v1-design.md): 8 skills,
3 commands, 1 agent, 2 hooks, 5 templates.

### Added
- **Skills** — `using-chimera` (bootstrap/router, injected every session),
  `designing-tasks`, `writing-plans`, `test-driven-development`,
  `exploring-reproducibly`, `verifying-before-done`,
  `debugging-systematically`, `finishing-a-branch`. Seven adapted from
  Superpowers (Jesse Vincent, MIT) with mode-awareness added;
  `exploring-reproducibly` written from scratch (pinned data, seeds,
  findings log, stopping rules, promotion rule).
- **Mode system** — every task declares build | exploration at kickoff;
  every loop stage has mode-specific behavior.
- **`/start-task`** — the loop: gate → mode → design → plan → execute →
  verify → finish (review gate inside), with a 3-attempt circuit breaker
  and plan-file resume.
- **`/design-project`** — project genesis: PRD (app-shaped, or ML-shaped
  via CRISP-DM phases 1-2), architecture ADRs, system design (module I/O
  contracts), roadmap backlog.
- **`/new-project`** — thin scaffolding (CLAUDE.md from template,
  gitignore, docs skeleton); never overwrites without a diff + approval.
- **`code-reviewer` agent** (read-only tools) — confidence gates,
  pre-report proof requirements, "zero findings is a valid review",
  false-positive skip list (adapted from Everything Claude Code, affaan-m,
  MIT), plus build and exploration (methodology) rubrics.
- **Hooks** — SessionStart bootstrap injection on `startup|clear|compact`;
  warn-only branch nudge on source edits on main/master (never blocks;
  resolves the edited file's git context; `CHIMERA_SILENCE_NUDGE=1` mutes).
- **Templates** — `CLAUDE.user.md`, `CLAUDE.project.md`, `prd-app.md`,
  `prd-ml.md`, `system-design.md`.
- **Tests & docs** — hook test scripts under `tests/`;
  `docs/update-procedure.md` (three-layer plugin update path);
  `docs/testing/smoke.md` (manual end-to-end matrix).
