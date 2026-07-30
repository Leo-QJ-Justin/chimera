#!/usr/bin/env bash
# tests/test-session-start.sh — validates the SessionStart injection JSON shape.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT=$(bash "$ROOT/hooks/session-start" 2>/dev/null); RC=$?
export CHIMERA_TEST_OUT="$OUT"
python3 - "$RC" <<'PY'
import json, os, sys
rc = int(sys.argv[1]); data = os.environ["CHIMERA_TEST_OUT"]
assert rc == 0, f"exit {rc}"
j = json.loads(data)
h = j["hookSpecificOutput"]
assert h["hookEventName"] == "SessionStart", h
ctx = h["additionalContext"]
assert "using-chimera" in ctx, "skill name missing from context"
assert "Routing" in ctx, "routing table missing from context"
assert len(ctx) > 500, f"context suspiciously short ({len(ctx)} chars)"
assert "additional_context" not in j, "legacy field must not be emitted"
print("PASS session-start shape")
PY
