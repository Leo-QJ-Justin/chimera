---
description: Produce a chimera improvement spec from field experience - collect friction events, quality-gate them, write a spec for the plugin repo
argument-hint: "[project phase or scope to retrospect | blank]"
---

# /retrospect

**Input**: $ARGUMENTS

Produce a chimera improvement spec from field experience. Invoke after
significant field use of chimera (a project phase completed, a run of
tasks through the loop), or when your human partner asks for a
retrospective. The output format: per change — target file, the edit,
a self-contained rationale citing the observed event inline.

1. **Collect candidates.** Walk the project's history for friction
   events: post-merge corrections, improvised ceremony, decisions
   relitigated after implementation, interrupts where the human forced
   a step chimera did not prescribe, skills that were wrong or silent
   when needed.
2. **Quality-gate each candidate** — actually read the files:
   - Observed, not invented: the rationale must cite a real event.
     A hypothetical failure is not a candidate.
   - Reusable, not one-off: would this bite a different project?
     Project-specific lessons go to the project's CLAUDE.md or memory,
     not the plugin.
   - Overlap check: grep the chimera skills and commands for existing
     coverage; prefer amending an existing skill over creating a new
     one.
   - Form check: match the edit's form to the failure type
     (prohibition + rationalization row / required template slot /
     positive recipe / routing row).
3. **Verdict per candidate:** Adopt / Improve then adopt / Absorb into
   an existing change / Drop. Dropped candidates are listed with one
   line of reasoning — a dropped lesson re-surfaces otherwise.
4. **Write the spec** to `docs/chimera-improvements-<date>.md` in the
   consuming project, in STE register (chimera:writing-in-ste),
   self-contained for an agent with no project context. Present it for
   your human partner's review; the plugin edit itself is a separate,
   approved task in the chimera repository.

The command never edits the plugin directly, and never runs
automatically — retrospection is invoked, not hooked. Each adopted
change's observed-event rationale becomes its pressure scenario when
the plugin edit lands (`docs/testing/pressure-scenarios/`).
