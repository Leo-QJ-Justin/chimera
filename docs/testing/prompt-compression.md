# Skill prompt compression

Measured on 2026-09-12 against the v1.10 tree at `142be6c`. Counts use
`re.findall(r"\S+", text)` over complete files, including frontmatter.
Enforced by `tests/check-skill-budgets.py`.

## Main skills

| Skill | Before | After | Ceiling |
|---|---:|---:|---:|
| `using-chimera` | 458 | 458 | 500 |
| `designing-tasks` | 1,702 | 1,128 | 1,300 |
| `writing-plans` | 1,016 | 911 | 950 |
| `test-driven-development` | 1,316 | 1,021 | 1,050 |
| `verifying-before-done` | 842 | 632 | 700 |
| `finishing-a-branch` | 1,297 | 1,085 | 1,150 |
| `debugging-systematically` | 1,186 | 943 | 1,050 |
| `exploring-reproducibly` | 815 | 733 | 760 |
| `creating-skills` | 933 | 807 | 850 |
| `writing-in-ste` | 997 | 792 | 820 |
| `writing-comparative-reports` | 851 | 851 | 900 |
| `persistent-model-discovery` | 565 | 549 | 600 |
| **Total** | **11,978** | **9,910** | - |

The main skill corpus decreased by 2,068 words (17.3 percent). Skill
descriptions are each at most 30 words and 200 characters.

## `using-chimera` is deliberately not compressed

A compression pass reduced this file to 136 words to meet the 150-word
always-loaded rule in `creating-skills`. That change was reverted, and the
ceiling was raised to 500 instead. Reasons:

- The routing table's left column is the keyword-matching surface. The
  compressed form replaced trigger descriptions with bare labels — "Bug,
  test failure, unexpected behavior" became "Bug", and "About to claim done
  / fixed / passing" became "Completion claim". `creating-skills` requires
  triggers to be keyword-rich: symptoms, error strings, synonyms, and
  "about to violate" moments. Removing the synonyms removes the match.
- The Red Flags table was dropped for one summary line covering three of
  its six rationalizations. "It's exploration, discipline doesn't apply"
  and "I'll just explore the code first" had no replacement.
- The definitions of **task** and **mode** were removed, while
  `/start-task` Phase 1 still asks which mode applies.
- It was not necessary. Restoring the full file costs 322 words, and the
  ordinary build bundle still lands under its own ceiling.

The 150-word rule was never calibrated for a 13-route table plus its
rationalizations. The ceiling is the thing that was wrong.

Scenario `change-23` pressure-tests the routing surface, so a future
compression of this file has a walk to fail.

## Workflow bundles

The build bundle contains `using-chimera`, `designing-tasks`,
`writing-plans`, `test-driven-development`, `verifying-before-done`, and
`finishing-a-branch`. Before this change, every build also loaded the
1,315-word `writing-good-tests.md` reference. That reference now loads only
for mocks or fakes, test helpers or cleanup, artifact tests, or nontrivial
expected-value construction.

| Bundle | Before | After | Ceiling | Reduction |
|---|---:|---:|---:|---:|
| Ordinary build | 7,940 | 5,235 | 5,300 | 34.1 percent |
| Tabular EDA | 8,964 | 7,238 | 7,500 | 19.3 percent |

Most of the build reduction is the conditional reference, not the prose
edits: it cuts what loads rather than what enforces.

Statistical-test guidance likewise loads only for an inferential claim,
test selection, or a group judgment beyond the observed sample.

## Ceilings: two bases

**Always-loaded and main skills** carry ceilings derived from what a bundle
can afford. They bind.

**Conditional references** load only when their trigger fires, so they do
not accumulate in the ordinary bundle. Their ceilings are round numbers
with real headroom, deliberately not current size plus a small margin: a
ceiling two percent above today's word count freezes a file rather than
constraining it, and passes forever without having said anything.

## Preservation checks

Read-only walks against the edited surfaces passed these scenarios:

- `change-01`, `change-03`, `change-04`, `change-05`, `change-06`,
  `change-07`, `change-09`.
- `change-14`, `change-15`, `change-17`, `change-18`, `change-21`.

Scenarios `change-02`, `change-08`, `change-11` to `change-13`,
`change-16`, `change-19`, `change-20`, and `change-22` were not rerun:
their behavior-bearing bodies did not change.

Additional probes passed:

- All 13 `using-chimera` routes select their previous target.
- Descriptive EDA does not load statistical tests; inference does.
- Normal build, exploration, detached HEAD, discard, Amendment, Split, and
  Step 0b integration paths each have one non-conflicting instruction.
- TDD retains RED, verify RED, GREEN, verify GREEN, REFACTOR, the
  deterministic boundary, and the promotion rule.
- Verification retains fresh evidence, aggregate instances, regression
  RED/GREEN, and requirement checks.
- Debugging retains its four ordered phases and the three-failed-fixes
  architecture stop.

**Known gap in this evidence.** The walks above were run by the agent that
made the edits, and twelve of twenty-two scenarios were rerun. Treat the
list as a record of what was checked, not as an independent result.

## The author-side mutation check now loads conditionally

`The Mutation Check` lives in `writing-good-tests.md`, so a plain TDD cycle
with no mocks no longer loads it. This is a deliberate reallocation, not an
oversight: v1.10 improvement H puts an *executed* mutation check in the
`code-reviewer` agent, which runs at every build review and produces
evidence rather than an author's recollection.

## Enforcement

```bash
python3 tests/check-skill-budgets.py --enforce
```

`--report` prints the same measurements without failing. Positional paths
restrict checks to specific registered files.
