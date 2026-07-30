---
name: using-chimera
description: Use when starting any conversation in a chimera-equipped project - establishes how to find and use chimera skills and commands before any response or action
---

# Using Chimera

Chimera is your development harness: an opt-in loop with two modes.
**Task** = one trip through the loop (app feature, pipeline, EDA pass,
experiment, spike). **Mode** = build (code we keep) or exploration (an
answer we act on).

## The Rule

If there is even a 1% chance a chimera skill or command applies, invoke it
BEFORE any other response or action - including clarifying questions. If it
turns out wrong for the situation, you don't have to follow it through.

Announce "Using [skill] to [purpose]". If a skill has a checklist, create a
todo per item.

(If you were dispatched as a subagent to execute a specific task, ignore
this skill.)

## Routing

| Situation | Invoke |
|---|---|
| New project idea (greenfield) | `/design-project` |
| Start any unit of work (feature, pipeline, analysis, experiment, spike) | `/start-task` |
| Scaffold chimera files into a repo | `/new-project` |
| About to write implementation code (build mode) | chimera:test-driven-development |
| About to run analysis/experiments (exploration mode) | chimera:exploring-reproducibly |
| Bug, test failure, unexpected behavior | chimera:debugging-systematically |
| About to claim done / fixed / passing | chimera:verifying-before-done |
| Work complete, deciding integration | chimera:finishing-a-branch |
| Creating or editing a skill | chimera:creating-skills |

Process skills come first; they set the approach.

## Red Flags

| Thought | Reality |
|---|---|
| "This is just a simple question" | Questions are tasks. Check the routing table. |
| "Quick change, no need for the loop" | Quick changes on main are fine - but the moment it becomes a task, /start-task. |
| "I remember how this skill works" | Skills evolve. Read the current version. |
| "The skill is overkill here" | Simple things become complex. Invoke it; drop it only if truly wrong. |
| "I'll just explore the code first" | Skills tell you HOW to explore. Check first. |
| "It's exploration, discipline doesn't apply" | Exploration has its own discipline: chimera:exploring-reproducibly. |

## Precedence

User instructions (CLAUDE.md, direct requests) > chimera skills > defaults.
Direct-on-main docs/chore edits need no ceremony - discipline is opt-in by
entering the loop, and strict once inside.
