#!/usr/bin/env bash
# tests/test-branch-nudge.sh — behavior matrix for the warn-only branch nudge.
set -u
HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/branch-nudge.py"
PASS=0; FAIL=0
t() { # name, want_warn(0|1), file, extra_env
  local name="$1" want_warn="$2" file="$3" env_extra="${4:-}"
  local out rc
  out=$(echo "{\"tool_input\":{\"file_path\":\"$file\"}}" | env $env_extra python3 "$HOOK" 2>&1); rc=$?
  if [ $rc -ne 0 ]; then echo "FAIL $name (exit $rc)"; FAIL=$((FAIL+1)); return; fi
  if [ "$want_warn" = 1 ] && ! echo "$out" | grep -q "start-task"; then
    echo "FAIL $name (no warning)"; FAIL=$((FAIL+1)); return; fi
  if [ "$want_warn" = 0 ] && [ -n "$out" ]; then
    echo "FAIL $name (unexpected output: $out)"; FAIL=$((FAIL+1)); return; fi
  echo "PASS $name"; PASS=$((PASS+1))
}
# fixture repos
T=$(mktemp -d); git -C "$T" init -qb main; touch "$T/app.py" "$T/notes.md"
mkdir -p "$T/docs"; touch "$T/docs/x.rst"
B=$(mktemp -d); git -C "$B" init -qb main; git -C "$B" checkout -qb feat/x; touch "$B/app.py"
N=$(mktemp -d); touch "$N/app.py"
t "source-on-main-warns"      1 "$T/app.py"
t "md-on-main-silent"         0 "$T/notes.md"
t "docs-dir-on-main-silent"   0 "$T/docs/x.rst"
t "feature-branch-silent"     0 "$B/app.py"
t "non-git-silent"            0 "$N/app.py"
t "env-silences"              0 "$T/app.py" "CHIMERA_SILENCE_NUDGE=1"
# notebook_path key (NotebookEdit tool)
out=$(echo "{\"tool_input\":{\"notebook_path\":\"$T/eda.ipynb\"}}" | python3 "$HOOK" 2>&1); rc=$?
if [ $rc -eq 0 ] && echo "$out" | grep -q "start-task"; then
  echo "PASS notebook-on-main-warns"; PASS=$((PASS+1))
else
  echo "FAIL notebook-on-main-warns"; FAIL=$((FAIL+1)); fi
rm -rf "$T" "$B" "$N"
echo "== $PASS passed, $FAIL failed"; [ $FAIL -eq 0 ]
