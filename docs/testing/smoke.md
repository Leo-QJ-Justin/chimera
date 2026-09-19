# chimera — Manual smoke test matrix

Run after every version bump, before pushing to the marketplace.
Estimated time: ~20 minutes (scripted checks ~1 minute; manual flows the
rest).

Sections 1 to 6 are interactive flows: run them in an interactive session.
In print mode the model rationalizes past approval gates and subagent
dispatch (observed in the v1.10.0 run), so a print-mode run is not a smoke
run.

## 0. Scripted checks (always first)

```bash
bash tests/test-branch-nudge.sh      # 7 cases, all PASS
bash tests/test-session-start.sh     # JSON shape PASS
python3 -c "import json;[json.load(open(f)) for f in ['hooks/hooks.json','.claude-plugin/plugin.json','.claude-plugin/marketplace.json']];print('OK')"
# the two version files must agree (they silently drifted once)
python3 -c "import json;a=json.load(open('.claude-plugin/plugin.json'))['version'];b=json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'];assert a==b,(a,b);print('version OK',a)"
# skill, description, reference, and cumulative workflow context budgets
python3 tests/check-skill-budgets.py --enforce
# user-agnostic guard: no personal names or conversation references in
# operational surfaces (author metadata in manifests is the only allowed
# personal reference). docs/ is scanned too - scenarios and specs are
# written from real projects and are where project detail leaks in.
! grep -rn "Leo\b\|in conversation" skills commands agents templates docs/testing docs/specs README.md CHANGELOG.md | grep -v "Leo-QJ"
```

## 1. Bootstrap injection

Install/update the plugin (see [update-procedure](../update-procedure.md)),
start a fresh session, and confirm the context contains the
`CHIMERA_BOOTSTRAP` block with the routing table. Then `/clear` and confirm
it's re-injected.

## 2. Branch nudge behavior

In a throwaway repo on `main`:
- Ask Claude to edit a `.py` file → expect the one-line nudge in the
  transcript, edit NOT blocked.
- Ask Claude to edit a `.md` file → no nudge.
- `export CHIMERA_SILENCE_NUDGE=1`, edit a `.py` → no nudge.

## 3. `/new-project` (throwaway dir)

Empty dir → `/new-project`. Expect: git initialized on `main`, `.gitignore`
with `plans/` + `.worktrees/`, CLAUDE.md from template with only *verified*
commands filled, `docs/{specs,findings,adr}` created, one scaffold commit.
Re-run in the same dir → must show a diff and ask before touching the
existing CLAUDE.md.

## 4. `/start-task` — build mode (throwaway repo)

Task: "add a slugify function". Expect, in order: branch created off main
(Phase 0); mode question answered `build` (Phase 1); spec written to
`docs/specs/` and approval requested (Phase 2); plan in `plans/` gitignored
(Phase 3) carrying a `## Preconditions` section (or "none") and an empty
`## Deviations`; preconditions run before task 1 (Phase 4); TDD cycle
visibly RED→GREEN (failing test run shown before implementation) (Phase
4); fresh verification run (Phase 5); review-gate dispatch reporting a
mutation and the tests it turned red, then Step 0b walking the spec's
Decisions entries to a home (a home that needs your answer is asked for
before the menu, not beside it), then the 3-option menu (Phase 6).

## 5. `/start-task` — exploration mode (throwaway repo with a CSV)

Task: "is column A correlated with column B?". Expect: research brief with
the "what result would change what decision" line; experiment plan with a
stopping rule; the analysis, a notebook under `notebooks/` or a committed
script, naming the pinned snapshot; findings doc in `docs/findings/`
ending with a `Decision:` line; any aggregate reported together with the
differing instances behind it under a stated cap; clean rerun before
numbers are reported; methodology review at finish.

## 6. `/design-project` (conversation only, no scaffold needed)

Prompt: "an app that tracks my reading list". Expect: type question, and
no distill question because no prior corpus exists → one-at-a-time
discovery questions → prd-app template filled, carrying the STE register
line, a Terms table, FR blocks with testable `Done when` lines, a guard
metric, and every `[ASSUMPTION]` tag reaching the index → the six-item
self-check run before the approval gate, including the rule that
"required"/"essential"/"mandatory" name exactly the values whose absence
stops acceptance → architecture tradeoffs recorded
as ADRs with status, tier, reversal-cost, and confidence lines, with the
confidence tags not all reading `[High]` → system-design module table
with a mermaid data flow and a risk table whose rows carry detection
signals → roadmap table whose rows name outcomes rather than methods,
with modes, a `Realizes` column whose IDs resolve
to PRD requirements, at least one gate row, and the critical-path and
parallel footer notes → Phase 5 scaffolds via /new-project and commits
genesis with no further gate. Confirm all four docs exist and are
committed.

The reading-list prompt has no model component, so system design must
carry **no** AI properties section. A `Boundary` column appears only if
the design marks a module probabilistic, and that module then names a
fail-closed contract. To exercise the AI sections, run a second pass on "a support assistant that answers from our
internal docs" and confirm `docs/system-design.md` gains the AI
properties section with all four memory layers decided, an evaluation
metric that is not the word "accuracy", cost arithmetic whose prices are
marked `[assumed — verify]`, and a `Boundary` column splitting the
retrieval modules from the generating one. Sections not needed say "none"
with a reason rather than sitting blank.

## Pass criteria

Every expectation above observed; no hook ever blocks an edit; no step
proceeds past an approval gate without asking.
