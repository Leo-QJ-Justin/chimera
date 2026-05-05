# Task Plan: chimera v0.2 — Beads integration

## Goal
Integrate `bd` (beads CLI) into chimera's `/start-feature` for dependency-aware backlog tracking, plus document the manual smoke procedure.

## Current Phase
Phase 1 — Rewrite commands/start-feature.md

## Plan reference
docs/superpowers/plans/2026-05-05-v0.2-beads-integration.md

## Spec reference
docs/superpowers/specs/2026-05-05-v0.2-beads-integration-design.md

## Phases
### Phase 1 — Rewrite commands/start-feature.md to v0.2 (8-step pipeline)
- **Status:** in_progress
### Phase 2 — Create docs/testing/smoke.md
- **Status:** pending
### Phase 3 — Bump version to 0.2.0 (plugin.json + marketplace.json)
- **Status:** pending
### Phase 4 — Add v0.2.0 entry to CHANGELOG.md
- **Status:** pending

## Decisions Made
| Decision | Rationale |
|---|---|
| chimera owns `bd` verbs directly (no bundle dep) | Recon: beadpowers stale (8★, 4mo); hyperpowers has zero `bd` calls despite tagline |
| Step 0 verify-branch first (was Step 5) | Hit spec-write block twice during chimera bootstrap; 3-line reorder |
