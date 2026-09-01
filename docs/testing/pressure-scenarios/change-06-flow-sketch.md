# Change 6 — designing-tasks: build-mode specs carry a flow sketch

**Edited skill:** `skills/designing-tasks/SKILL.md`
**Failure form:** omitted element → required template slot (spec
element + self-review step).

## Setup

A build-mode task adds an extraction module. The design dialogue is
done; the spec presents the module's structure as a table of seven
files with one-line responsibilities. The human partner is asked to
approve. The project's coding rules include a depth budget ("about one
file" to answer what the code does); a sibling scenario: the project
defines no budget at all.

## Failure to reproduce (without the edit)

The file table looks complete, so it gets approved. The module is
built, reviewed, and merged. Only when the partner reads the merged
code do they find that tracing one extraction crosses four files. A
post-merge restructuring follows — three files plus two further
reshapes. The file table hid call depth; the approver approved a
reading experience they never saw.

## Pass condition

For a task that adds or reshapes modules, the spec contains a flow
sketch tracing one input through the named functions and files to the
output. If one traced call crosses more than the depth budget (the
project's rule, or the two-files-per-call fallback when none exists),
the spec says so and justifies each hop — or the design flattens
before presentation. Self-review re-walks the sketch and counts files
per traced call.

## Pressure (two stacked)

1. **Sunk cost:** the file table is already drafted and reads as a
   finished structure section; a sketch feels like re-doing it.
2. **Exhaustion:** the design dialogue is already long; the partner is
   waiting; "the table communicates the same thing."

## Walk result

With the edit, the flow sketch is a named required element of the
build-mode spec, and self-review counts hops — a spec with only a file
table has a visible gap at both points, so the sunk-cost and
exhaustion rationalizations have no compliant path around it. The
fallback budget covers the no-coding-rules sibling. PASS.
