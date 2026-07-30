#!/usr/bin/env python3
"""Warn-only nudge: editing source files on main/master suggests /start-task.

Never blocks (always exit 0). Git context is resolved from the edited file's
directory, not the CWD. Spec: docs/specs/2026-07-29-chimera-v1-design.md §3.2
"""
import json
import os
import subprocess
import sys

DOC_BASENAMES = ("CHANGELOG", "README", "LICENSE")
DOC_EXACT = (".gitignore", ".gitattributes", ".editorconfig")


def is_doc(path: str) -> bool:
    base = os.path.basename(path)
    return (
        path.endswith(".md")
        or "/docs/" in path.replace(os.sep, "/")
        or base in DOC_EXACT
        or any(base.startswith(p) for p in DOC_BASENAMES)
    )


def main() -> int:
    if os.environ.get("CHIMERA_SILENCE_NUDGE") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
        ti = payload.get("tool_input", {})
        path = ti.get("file_path") or ti.get("notebook_path") or ""
    except Exception:
        return 0
    if not path or is_doc(path):
        return 0
    workdir = os.path.dirname(os.path.abspath(path)) or "."
    if not os.path.isdir(workdir):
        workdir = os.getcwd()
    branch = ""
    for cmd in (["rev-parse", "--abbrev-ref", "HEAD"],
                ["symbolic-ref", "--short", "HEAD"]):  # fallback: unborn branch (fresh repo)
        try:
            r = subprocess.run(
                ["git", "-C", workdir] + cmd,
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            return 0
        if r.returncode == 0:
            branch = r.stdout.strip()
            break
    if not branch:
        return 0  # not a git repo
    if branch in ("main", "master"):
        print(
            "chimera: editing source on {} - for task work, /start-task will "
            "branch first. (CHIMERA_SILENCE_NUDGE=1 to mute)".format(branch),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
