# Global preferences

## Git
- Conventional Commits: `type(scope): summary` - types: feat, fix, docs,
  refactor, test, chore, build.
- Never include "Co-Authored-By" or tool-generated footers in commits or
  PR bodies.
- Subagents MUST NOT commit. The main agent reviews subagent work, then
  commits.
- Feature work and multi-file changes happen on branches - enter via
  /start-task, never directly on main. (Docs and small chores on main are
  fine.)

## New projects
- Always add `plans/` to `.gitignore` (plan files are working state).

## Documentation lookup
- Use Context7 (or the project's pinned docs) when implementing with
  unfamiliar libraries - verify APIs, don't guess.

## Frontend work
- Before UI code: invoke frontend-design AND ui-ux-pro-max skills
  (complementary: implementation quality + design intelligence).

## Workflow
- The chimera plugin owns the development loop (/design-project,
  /start-task, /new-project). Project specifics live in each project's
  CLAUDE.md - keep this file to durable preferences only.
