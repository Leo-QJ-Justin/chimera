#!/usr/bin/env python3
"""Measure and enforce Chimera skill context budgets."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Two tiers, set on different bases.
#
# ALWAYS-LOADED AND MAIN SKILLS: ceilings come from what a workflow bundle can
# afford, and they bind. `using-chimera` is the documented exception to the
# 150-word rule in creating-skills: the hook injects it verbatim every session,
# and it carries 13 routes plus their rationalizations. Its triggers are the
# keyword-matching surface - compressing "Bug, test failure, unexpected
# behavior" to "Bug" costs the synonyms that make the route fire. 150 words was
# never calibrated for a 12-skill routing table; 500 is, and the build bundle
# still lands under its own ceiling with the full table present.
#
# CONDITIONAL REFERENCES: these load only when their trigger fires, so they do
# not accumulate in the ordinary bundle. Their ceilings are round numbers with
# real headroom, NOT current size plus a margin - a ceiling 2% above today's
# word count freezes the file instead of constraining it, and passes forever
# without ever having said anything.
FILE_BUDGETS = {
    "skills/using-chimera/SKILL.md": 500,
    "skills/designing-tasks/SKILL.md": 1300,
    "skills/writing-plans/SKILL.md": 950,
    "skills/test-driven-development/SKILL.md": 1050,
    "skills/verifying-before-done/SKILL.md": 700,
    "skills/finishing-a-branch/SKILL.md": 1150,
    "skills/debugging-systematically/SKILL.md": 1050,
    "skills/exploring-reproducibly/SKILL.md": 760,
    "skills/creating-skills/SKILL.md": 850,
    "skills/writing-in-ste/SKILL.md": 820,
    "skills/writing-comparative-reports/SKILL.md": 900,
    "skills/persistent-model-discovery/SKILL.md": 600,
    "skills/test-driven-development/writing-good-tests.md": 1500,
    "skills/exploring-reproducibly/analysis-style.md": 800,
    "skills/exploring-reproducibly/playbook-generic.md": 800,
    "skills/exploring-reproducibly/playbook-stat-tests.md": 700,
    "skills/exploring-reproducibly/playbook-tabular.md": 1100,
    "skills/exploring-reproducibly/playbook-text.md": 1100,
    "skills/exploring-reproducibly/playbook-images.md": 1100,
    "skills/exploring-reproducibly/playbook-time-series.md": 1250,
    "skills/finishing-a-branch/post-loop-paths.md": 600,
}

WORKFLOW_BUDGETS = {
    "build": (
        5300,
        (
            "skills/using-chimera/SKILL.md",
            "skills/designing-tasks/SKILL.md",
            "skills/writing-plans/SKILL.md",
            "skills/test-driven-development/SKILL.md",
            "skills/verifying-before-done/SKILL.md",
            "skills/finishing-a-branch/SKILL.md",
        ),
    ),
    "tabular-eda": (
        7500,
        (
            "skills/using-chimera/SKILL.md",
            "skills/designing-tasks/SKILL.md",
            "skills/writing-plans/SKILL.md",
            "skills/exploring-reproducibly/SKILL.md",
            "skills/exploring-reproducibly/analysis-style.md",
            "skills/exploring-reproducibly/playbook-generic.md",
            "skills/exploring-reproducibly/playbook-tabular.md",
            "skills/verifying-before-done/SKILL.md",
            "skills/finishing-a-branch/SKILL.md",
        ),
    ),
}

DESCRIPTION_WORD_LIMIT = 30
DESCRIPTION_CHARACTER_LIMIT = 200


def count_words(text: str) -> int:
    """Count whitespace-delimited prompt words."""
    return len(re.findall(r"\S+", text))


def read_description(path: Path) -> str:
    """Read one single-line description from skill frontmatter."""
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing frontmatter")

    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ValueError("unclosed frontmatter") from error

    matches = [line for line in lines[1:end] if line.startswith("description:")]
    if len(matches) != 1:
        raise ValueError("description must be one frontmatter line")

    description = matches[0].partition(":")[2].strip().strip("\"'")
    if not description:
        raise ValueError("description is empty")
    return description


def relative_path(argument: str) -> str:
    """Normalize a user-supplied path relative to the repository root."""
    path = Path(argument).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def measure_file(relative: str) -> int:
    """Return the word count for one repository file."""
    return count_words((ROOT / relative).read_text())


def check_file(relative: str) -> tuple[list[str], list[str]]:
    """Return report lines and failures for one registered file."""
    reports: list[str] = []
    failures: list[str] = []
    path = ROOT / relative
    if not path.is_file():
        return reports, [f"MISSING {relative}"]

    words = measure_file(relative)
    limit = FILE_BUDGETS[relative]
    reports.append(f"FILE {relative}: {words}/{limit} words")
    if words > limit:
        failures.append(f"OVER {relative}: {words}/{limit} words")

    if path.name == "SKILL.md":
        try:
            description = read_description(path)
        except ValueError as error:
            failures.append(f"FRONTMATTER {relative}: {error}")
        else:
            description_words = count_words(description)
            description_characters = len(description)
            reports.append(
                "DESCRIPTION "
                f"{relative}: {description_words}/{DESCRIPTION_WORD_LIMIT} words, "
                f"{description_characters}/{DESCRIPTION_CHARACTER_LIMIT} chars"
            )
            if description_words > DESCRIPTION_WORD_LIMIT:
                failures.append(
                    f"DESCRIPTION-WORDS {relative}: "
                    f"{description_words}/{DESCRIPTION_WORD_LIMIT}"
                )
            if description_characters > DESCRIPTION_CHARACTER_LIMIT:
                failures.append(
                    f"DESCRIPTION-CHARS {relative}: "
                    f"{description_characters}/{DESCRIPTION_CHARACTER_LIMIT}"
                )
    return reports, failures


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--enforce", action="store_true")
    parser.add_argument("paths", nargs="*")
    return parser.parse_args()


def main() -> int:
    """Report registered budgets and fail when enforced limits are exceeded."""
    args = parse_args()
    selected = [relative_path(path) for path in args.paths]
    unknown = sorted(set(selected) - FILE_BUDGETS.keys())
    if unknown:
        for relative in unknown:
            print(f"UNREGISTERED {relative}")
        return 1

    files = selected or list(FILE_BUDGETS)
    reports: list[str] = []
    failures: list[str] = []
    for relative in files:
        file_reports, file_failures = check_file(relative)
        reports.extend(file_reports)
        failures.extend(file_failures)

    if not selected:
        for name, (limit, members) in WORKFLOW_BUDGETS.items():
            words = sum(measure_file(member) for member in members)
            reports.append(f"WORKFLOW {name}: {words}/{limit} words")
            if words > limit:
                failures.append(f"OVER-WORKFLOW {name}: {words}/{limit} words")

    for line in reports:
        print(line)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1 if args.enforce else 0
    print("PASS skill context budgets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())