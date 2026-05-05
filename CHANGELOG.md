# Changelog

All notable changes to chimera are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [0.1.0] - 2026-05-05

### Added
- `/start-feature` command — orchestrates Superpowers brainstorm/plan/execute with planning-with-files persistence and a branch-enforcement guard.
- `PreToolUse` hook on `Write|Edit|NotebookEdit` — blocks edits when current branch is `main` or `master`. No-ops in non-git directories.
- Plugin manifest, marketplace manifest, README, .gitignore, this changelog.

### Notes
- Bootstrapped from a single design session. Untested on real features yet — first iteration cycle is the next 3-5 features.
