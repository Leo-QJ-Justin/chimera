# chimera v1.0 — Manual smoke test matrix

Run after every version bump, before pushing to the marketplace.
Estimated time: ~20 minutes (scripted checks ~1 minute; manual flows the
rest).

## 0. Scripted checks (always first)

```bash
bash tests/test-branch-nudge.sh      # 7 cases, all PASS
bash tests/test-session-start.sh     # JSON shape PASS
python3 -c "import json;json.load(open('hooks/hooks.json'));json.load(open('.claude-plugin/plugin.json'));print('OK')"
# user-agnostic guard: no personal names or conversation references in
# operational surfaces (author metadata in manifests is the only allowed
# personal reference)
! grep -rn "Leo\b\|in conversation" skills commands agents templates README.md CHANGELOG.md | grep -v "Leo-QJ"
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
(Phase 3); TDD cycle visibly RED→GREEN (failing test run shown before
implementation) (Phase 4); fresh verification run (Phase 5); review-gate
dispatch + 3-option menu (Phase 6).

## 5. `/start-task` — exploration mode (throwaway repo with a CSV)

Task: "is column A correlated with column B?". Expect: research brief with
the "what result would change what decision" line; experiment plan with a
stopping rule; notebook under `notebooks/` naming the pinned snapshot;
findings doc in `docs/findings/` ending with a `Decision:` line; clean
rerun before numbers are reported; methodology review at finish.

## 6. `/design-project` (conversation only, no scaffold needed)

Prompt: "an app that tracks my reading list". Expect: type question →
one-at-a-time discovery questions → prd-app template filled → architecture
tradeoffs recorded as ADR → system-design module table → roadmap table with
modes → offer to scaffold. Abort before scaffold; confirm all four docs
exist and are committed.

## Pass criteria

Every expectation above observed; no hook ever blocks an edit; no step
proceeds past an approval gate without asking.
