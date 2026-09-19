# Notice

Chimera is MIT-licensed. It adapts MIT-licensed material from three
upstream projects. The per-skill attribution blockquotes were removed in
v1.10.0's context-budget pass — they cost context on every session load for
information the running agent never uses. This file is their one home
instead; nothing is unattributed.

## Upstreams

| Project | Author | License | What chimera adapts |
|---|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) | Jesse Vincent | MIT | the majority of the skill set — see per-skill table below |
| [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) | affaan-m | MIT | the review agent, Pattern Grounding, the learn-eval quality gate |
| [`danyuchn/asd-ste100-skill`](https://github.com/danyuchn/asd-ste100-skill) | danyuchn | MIT | `writing-in-ste`, ported whole |

## Per-file provenance

| chimera file | Upstream | Adaptation |
|---|---|---|
| `skills/designing-tasks` | Superpowers `brainstorming` | slimmed to task altitude, made mode-aware; project-level design moved to `/design-project` |
| `skills/writing-plans` | Superpowers `writing-plans` | plus ECC's Pattern Grounding and chimera's experiment-plan variant |
| `skills/test-driven-development` | Superpowers `test-driven-development` | plus chimera's deterministic boundary and promotion rule |
| `skills/verifying-before-done` | Superpowers `verification-before-completion` | — |
| `skills/debugging-systematically` | Superpowers `systematic-debugging` | — |
| `skills/finishing-a-branch` | Superpowers `finishing-a-development-branch` | chimera's review gate folded in as Step 0 |
| `skills/creating-skills` | Anthropic skill-creator guidance; Superpowers `writing-skills`; ECC learn-eval quality gate | synthesized |
| `skills/writing-in-ste` | `danyuchn/asd-ste100-skill` | ported |
| `agents/code-reviewer.md` | ECC code-reviewer; Superpowers reviewer template | attribution retained in-file |

## ASD-STE100

`skills/writing-in-ste` applies the principle of ASD-STE100 Issue 9
(January 2025), maintained by the Simplified Technical English Maintenance
Group. The standard's approved-word dictionary is **not** reproduced in
this repository; the principle behind it is applied instead. For
word-by-word compliance use the free official download at
<https://www.asd-ste100.org/>.
