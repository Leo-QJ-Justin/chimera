# Chimera improvement plan — v2

> Written in Simplified Technical English (ASD-STE100 register).
> Audience: an agent updating the chimera plugin, with no context of
> the source project. Each change names its target file, states the
> edit, and gives a self-contained rationale.
>
> Supersedes `chimera-improvements.md` (v1). Each change below carries
> a **Status vs v1** line: *unchanged*, *amended*, *restructured*, or
> *new*. Amended and restructured changes state what moved and why, so
> v1 and v2 can be compared change by change.

## Where the edits land

The chimera source repository is `/home/leoqi/dev/chimera` (git).
All file paths below are relative to that repository. Do not edit the
plugin cache under `~/.claude/plugins/`.

Files touched by this plan:

| File | Changes |
|---|---|
| `skills/designing-tasks/SKILL.md` | 1, 6, 7 |
| `commands/design-project.md` | 2, 8, 11 |
| `skills/writing-in-ste/SKILL.md` | 3 |
| `skills/finishing-a-branch/SKILL.md` | 4, 5 |
| `skills/using-chimera/SKILL.md` | 4, 2, 12 (routing rows) |
| `skills/writing-plans/SKILL.md` | 5 (deviation log) |
| `skills/exploring-reproducibly/SKILL.md` | 9 |
| `agents/code-reviewer.md` | 9 (rubric line) |
| `skills/writing-comparative-reports/SKILL.md` | 2 (new skill) |
| `agents/corpus-profiler.md` | 2 (new agent) |
| `skills/persistent-model-discovery/SKILL.md` | 8 (new skill) |
| `templates/prd-app.md`, `templates/prd-ml.md` | 8 |
| `templates/system-design.md` | 8 |
| `agents/eda-profiler.md` | one dispatch note only (v1 targeted its contract; v2 does not — see Change 2) |
| `docs/testing/pressure-scenarios/*.md` | 10 (new scenario files) |
| `commands/retrospect.md` | 12 (new command) |
| `docs/process-map.md` | 13 (new, living map) |
| `CLAUDE.md` (chimera repo) | 13 (same-commit map rule) |

## The organizing principle (read before the changes)

One retrospective insight drives Changes 2, 8, and 9. State it once
here so each change can reference it.

Evidence work can stop at three depths:

1. **Findings:** "here is what the evidence contains."
2. **Verdict:** "adopt / reject / park, because of these numbers."
3. **Binding constraint:** "the evidence imposes this constraint, we
   commit to it, and it has these named implications for the next
   phase."

Chimera today enforces depth 2 (the decision line in
`exploring-reproducibly` and the code-reviewer rubric). The source
project showed that depth 2 is not enough: two versions of a pilot
analysis passed the decision-line check and still left every
downstream design question open. The third version added no new
evidence. It reframed the same evidence as commitments — a
format-only requirement, a scope boundary, a field contract — each
with named implications ("the parser can assume the 3-file reference
structure", "the schema does not handle format conversion", "blocked
suppliers get manual workarounds, not system complexity"). Only then
could the next phase be designed.

The rule: **an evidence phase closes with binding constraints, each
written as evidence → constraint → implications — or an explicit
"no design consequence."** Change 9 installs the rule at task
altitude (every findings doc). Change 8 installs it at genesis
altitude (a BIND phase before PRD approval). Change 2 supplies the
evidence those constraints must trace to.

---

## Change 1 — designing-tasks: add a "Decisions" section to build-mode specs

**Status vs v1:** unchanged.

**Target:** `skills/designing-tasks/SKILL.md`, the "Mode Fork"
section, build-mode task spec bullet list; and checklist item 1.

**Edit (a):** Add one required spec section to the build-mode output:

> - Decisions: every judgment call the spec makes, listed as
>   *decision / rejected alternative / trigger to revisit*. A choice
>   the reader cannot find here is a choice the reader never approved.

**Edit (b):** Extend checklist item 1 ("Explore context"): when the
task realizes a requirement id (`FR-N`), the design dialogue
re-presents the requirement's enumerated content to the human partner
for re-confirmation ("FR-8 names these seven metrics — still all
wanted?") instead of citing the id as settled.

**Rationale:** In the source project, judgment calls buried in
approved spec prose were challenged by the human partner only after
implementation, four times, each causing a post-merge change (a
thread-split regex handling a second language nobody wanted; a
vendor-name hardcode; two telemetry metrics built into an eval and
then removed together with a PRD amendment; a module's internal
ordering). The one judgment call surfaced explicitly as a named
decision before build was the only one that never needed later
surgery. Requirement lists drafted at genesis get approved wholesale;
item-level approval only really happens when the items are re-shown
at task time.

**Interaction:** Change 7 is the mandatory partner of this change.
A Decisions section without Change 7 gives a correctness-path
heuristic a legitimate-looking place to hide ("it was recorded, the
spec was approved"). Land 1 and 7 together.

---

## Change 2 — /design-project: gate genesis on a data-contact spike

**Status vs v1:** amended. The gate is unchanged. The report contract
moves out of the `eda-profiler` agent into a new skill,
`writing-comparative-reports`, and the mechanical work gets its own
agent, `corpus-profiler` — the non-tabular sibling of `eda-profiler`.
The spike's findings report must close per the Change 9 rule.

The agent and the skill's narrative recipe are reverse-engineered
from the two exemplar documents the source project produced: a
profiling report (`email-thread-profiles.md`, regenerated by a
committed script) and the decision brief built on it
(`pilot-selection-brief-v3.md`). The design goal: dispatching the
agent and following the recipe reproduces documents of that shape
on any corpus.

**Target:** `commands/design-project.md` (new gate between Phase 1
brainstorm and PRD writing); new file
`skills/writing-comparative-reports/SKILL.md`; new file
`agents/corpus-profiler.md`; one routing row in
`skills/using-chimera/SKILL.md`.

### Edit (a) — the gate, in `/design-project`

Insert after the Phase 1 brainstorm, before the PRD is written: when
the project consumes an existing corpus or artifact format (files,
exports, logs, an API's real responses), the PRD is not written until
a data-contact spike completes:

1. Pin the sample set.
2. Locate the priority authority: the business document (reportout,
   charter, PRD draft) that field priorities will be judged against.
   If none exists, the human partner names priorities explicitly;
   priorities are never invented by the profiler.
3. Dispatch the `corpus-profiler` agent with the pinned set, the
   authority document, and the downstream decisions the profile must
   ground. Review its report and script; the main agent commits both
   (subagents never commit).
4. Close any evidence gaps the report flags as decision-blocking
   (targeted inspection of unreadable items, a missing population
   join) before writing the brief.
5. Write the decision brief from the profile per the "From profile
   to brief" recipe in `chimera:writing-comparative-reports`. Close
   it per the evidence-closure rule (Change 9): each adopted finding
   ends as evidence → constraint → implications, or "no design
   consequence." These constraints are the input to Phase 1b
   (Change 8).
6. Write the PRD against the brief. Observed counts freeze into
   test fixtures for the later build tasks. State explicitly: the
   report records observations, the tests state the contract — a
   deliberate divergence between them is a documented decision, not
   drift.

### Edit (b) — new skill `writing-comparative-reports`

Create `skills/writing-comparative-reports/SKILL.md`. Description:
"Use when writing a report that compares many instances of one kind
of thing — corpus profiling, tool comparison, log analysis — before
any instance is opened." The body carries two parts: the report
contract (how the profile is produced) and the narrative recipe (how
a decision brief is built on it).

**Part 1 — the report contract.** Compressed: rubric (with
consumers) → same rubric per item → cross-item table → per-item
verdicts → regenerate, never patch.

1. Rubric before reading: declare the questions, criteria, and field
   checklist before opening any instance. Per-item sections become
   comparable; "what we looked for" is auditable separately from
   "what we found".
2. Every criterion names its consumer — the downstream decision that
   reads it, or the authority document (business goals, charter)
   that justifies it. A criterion with no consumer leaves the
   rubric.
3. Define a location/provenance code alphabet once (e.g. one letter
   per layer of the artifact) and use it in every dive. The alphabet
   is what makes dispersion questions askable: "what is the smallest
   set of layers a consumer must read?"
4. Record negative evidence as diligently as positive: "absent from
   all X" is a stated verdict per criterion per item, never an
   omission. Escalation and cost decisions read the negatives.
5. Mechanism explainers ride with the numbers: a criterion that
   needs a nontrivial detector documents the mechanism, validates it
   with at least two independent signals, shows a worked example,
   and cites sources. Pre-label adjacent known hazards even when the
   sample contains none.
6. Two altitudes, both mandatory: a cross-item summary table for
   distribution questions (thresholds come from here) and per-item
   deep dives for existence and shape questions (edge cases come
   from here).
7. Every deep dive ends in a decision-relevant verdict, not a
   summary.
8. The rubric iterates on misses; the report regenerates whole from
   a committed script and is never hand-patched. Frozen counts
   become test fixtures.

**Part 2 — from profile to brief (the narrative recipe).** The
profile records what is; the brief decides what binds. These moves
are judgment — the human partner and the main agent make them, fed
by the profile's handoff sections (see the `corpus-profiler` output
contract):

1. **Join the population authority.** Connect profiled items to the
   volume or importance source (a tracking list, usage data). Every
   coverage claim ("these 5 = 51%") comes from this join; profiling
   counts alone rank nothing. If no authority exists, say so — the
   brief then carries enumeration claims only.
2. **Make the constraint move.** Take the dominant observation
   (e.g. "23 of 25 files are PDF"), state it as a candidate rule,
   classify **every** item against the rule (a tier table), and
   give every violator an explicit disposition — excluded, manually
   admitted with a revisit trigger, or fix-required. A constraint
   without a full classification and violator dispositions is an
   observation wearing a rule's name.
3. **Name a reference implementation.** Pick the cleanest exemplar
   under the rubric and map it completely — every field on every
   part, each designated (extracted / cross-check / not extracted).
   This is what "good" means, and what standardisation requests
   point at.
4. **Ground the contract bidirectionally.** Every required field is
   confirmed present in the evidence; every request to a partner
   exists because the field is already observable and carries a
   compliance count showing the ask is cheap; the whole contract is
   tested against the sample ("none rejects").
5. **Carry conflicts live.** Each observed self-contradiction (two
   values for one field) travels into the open-decisions section
   with its values and sources as the worked example.
6. **Label every claim** Observed / Interpretation / Recommendation,
   and state causal cautions ("region is shorthand for which
   suppliers sit there, not a cause").
7. **Close per the evidence-closure rule (Change 9):** each adopted
   finding ends as evidence → constraint → implications.

### Edit (c) — new agent `agents/corpus-profiler.md`

The non-tabular sibling of `eda-profiler`, with the same philosophy:
mechanical verdicts stated as decisions; judgment returned as
questions. It executes Part 1 of the skill and produces the handoff
sections Part 2 consumes.

Frontmatter: `name: corpus-profiler`; `tools: Read, Grep, Glob,
Bash, Write`; description: "Mechanical first-pass profiling of a
corpus of heterogeneous artifacts — emails, document packs, exports,
logs. Use when a data-contact spike needs per-item and cross-item
profiles before design begins — dispatched by /design-project's
data-contact spike, or on demand. Returns a profiling report
regenerated from a committed script, per
chimera:writing-comparative-reports. For a single tabular dataset,
dispatch eda-profiler instead."

**Dispatch parameters:** corpus path and the pinned sample set (echo
it back); the priority authority document; the downstream decisions
the profile must ground; a candidate field checklist if one exists;
output paths for the script and report.

**The Boundary (mirrors eda-profiler's):** state a consequence as a
decision ONLY when it is mechanical — a page with no extractable
text is a scan candidate; a container that nests is unpacked; a
field absent from every layer is absent. The agent MAY compute
constraint candidates ("23 of 25 items satisfy rule R; the
violators are X and Y") because counting is mechanical — but
adopting a rule, assigning priorities beyond the authority document,
choosing the pilot subset, and assigning ownership (we-fix / we-ask
/ business-decides) are judgment: they come back as questions under
`Judgment calls`. The agent writes only the profiling script and the
report at the given paths, and never commits — the main agent
reviews and commits.

**Procedure:**

1. **Rubric first**, per the skill: questions, criteria with
   consumers traced to the authority document, field checklist, and
   the location-code alphabet derived from the artifact's real layer
   structure — all declared before opening any item.
2. **Container metadata before heuristics:** enumerate the format's
   own declared fields and the reader library's API surface; only
   then invent detection heuristics over names or content. Run the
   format edge checklist with real probes: can the container nest
   itself? Can members be non-file objects? What happens on a
   corrupt member?
3. **One committed script regenerates everything.** Raw values
   verbatim (never normalized in the report); explicit negatives per
   field per item; verdicts at the finest real grain (per page, not
   per file, when pages exist).
4. **Validate every nontrivial detector** with two or more
   independent signals, a worked demonstration, and cited sources;
   pre-label adjacent known hazards the sample happens not to
   contain.
5. **Report at two altitudes** with a decision-relevant verdict per
   item.
6. **Emit the handoff sections** — the mechanical feedstock for the
   narrative recipe:
   - format census: formats, media, and sizes per item, with the
     computed constraint candidates and their violator lists;
   - exemplar ranking: which items score cleanest under the rubric
     (reference-implementation candidates);
   - conflict register: every field observed with two values in one
     item, both values and their location codes;
   - variation axes: what varies, across which grouping, and what
     stays stable when it does;
   - compliance counts: for each candidate standardisation ask,
     how many items already comply;
   - evidence gaps that block decisions: items whose content the
     mechanical pass cannot see (scans, encrypted members), named
     as targeted-inspection requests;
   - `Judgment calls`: every non-mechanical decision the corpus
     raises, phrased as observation plus what needs deciding. If
     none, say "None raised".

### Edit (d) — routing row in `using-chimera`

| Situation | Invoke |
|---|---|
| Profiling a corpus, comparing tools, analyzing logs — any many-instance investigation | chimera:writing-comparative-reports |

### Why not `eda-profiler` (v1 → v2)

The v1 spec targeted the `eda-profiler` agent prompt. That agent is a
deliberately narrow pandas mechanic over one tabular dataset: "you do
the typing, the analyst does the judgment," forbidden from writing
any file, output fixed as an Observations & Findings notebook draft.
The report contract wants nearly the opposite: a rubric declared
before reading, per-item deep dives with verdicts, a committed report
regenerated from a script. One agent cannot carry both contracts
without contradicting itself. The evidence also supports a skill for
the methodology: the contract was reused for a tool-comparison task
that never touched `eda-profiler` — and a tool comparison has no
dataset an agent could be dispatched on. So v2 splits the concern:
the methodology lives in the skill; the mechanical execution over a
corpus gets its own agent (`corpus-profiler`) that embeds the skill
the way `eda-profiler` embeds the analysis-style contract; and
`eda-profiler` stays exactly as it is, plus one dispatch note: "for
non-tabular corpora, dispatch corpus-profiler instead."

### Exemplar provenance (what the agent + recipe must reproduce)

The design is reverse-engineered from the source project's two
artifacts. The profiling report owed its usefulness to six
mechanisms, all now in Part 1 and the agent procedure: an authority
document behind every priority; the location-code alphabet that made
the dispersion question askable; explicit negatives (which enabled
the lazy-escalation design: 1 of 18 items needed OCR although 12 of
18 contained scans); detectors validated by independent bimodal
signals with adjacent hazards pre-labeled; two altitudes; script
regeneration freezing counts into fixtures. The decision brief owed
its narrative to the seven moves now in Part 2: the population join
(coverage arithmetic), the constraint move (dominant format →
candidate rule → full tier classification → violator dispositions),
the reference implementation (cleanest exemplar mapped field by
field with designations), bidirectional grounding (contract fields
confirmed present; asks priced by compliance counts; contract tested
against the sample), live conflicts carried into open decisions,
evidence labels on every claim, and closure per Change 9. Earlier
versions of the same brief had the profile but stopped at findings
and verdicts; only the version that made moves 2–4 unblocked design.

**Rationale (gate, unchanged from v1):** In the source project the
corpus-profiling phase was the highest-leverage work — every parser
threshold traced to it — but the human partner had to interrupt
`/design-project` to force it, and design vocabulary churned because
architecture was drafted before the corpus facts were in. Heuristics
invented before checking format metadata cost twice: the `.msg`
format's `hidden` flag made a hand-written logo-filename filter
unnecessary, and was found months later. Happy-path profiling missed
nested-message attachments and a library garbage-collection trap;
both surfaced late as review findings and runtime errors — hence the
edge checklist.

---

## Change 3 — writing-in-ste: define notation at first use

**Status vs v1:** unchanged.

**Target:** `skills/writing-in-ste/SKILL.md`, the rules table and the
process checklist.

**Edit:** Add a rule row and a checklist line:

> Every symbol, formula variable, or abbreviation gets a plain-word
> reading where it first appears. A document that must be parsed
> without a follow-up question fails the moment it uses undefined
> notation.

**Rationale:** A spec in the source project used set-difference
notation ($P \setminus G$) undefined; the human partner had to ask
what it meant — exactly the follow-up question the STE register
exists to prevent. A notation block beside the formulas resolved it.
The current rules table covers words, sentences, and terms, but has
no row for notation; this is a real gap, not a duplicate.

---

## Change 4 — finishing-a-branch: add an amendment path, and route to it

**Status vs v1:** amended. The path is unchanged. v2 adds a routing
row in `using-chimera`, because without it no session ever finds the
path.

**Target:** `skills/finishing-a-branch/SKILL.md`, new section after
"Step 5: Execute Choice"; and the routing table in
`skills/using-chimera/SKILL.md`.

**Edit (a)** — the path:

> ## Amendment path
>
> For post-merge scope corrections: a small behavior change to
> already-integrated work, requested after the loop closed. No spec,
> no plan. Requirements: (a) tests move with the change; (b) every
> document that states the amended behavior — spec, PRD, system
> design — moves in the same commit; a requirement label that no
> longer matches shipped behavior is stale. Micro-branch optional;
> full test suite before the merge or commit, as always.

**Edit (b)** — routing row in `using-chimera`:

| Situation | Invoke |
|---|---|
| Small behavior change to already-merged work | chimera:finishing-a-branch (Amendment path) |

### Why the routing row was added (v1 → v2)

`finishing-a-branch` triggers when an open task completes. An
amendment request arrives when no task is open. Under the current
routing table, such a request either gets forced through full
`/start-task` (too heavy, so the ceremony gets skipped) or handled as
a direct-on-main edit with no rules — which is exactly how the source
project improvised it four times. A path that nothing routes to is
documentation, not process.

**Rationale (path, unchanged from v1):** The source project made four
post-merge amendments and improvised the ceremony each time; the only
rule that kept the docs truthful ("docs move with code in the same
commit") was session culture, recorded nowhere.

---

## Change 5 — deviations: logged during execution, briefed to the reviewer as questions

**Status vs v1:** amended. The reviewer-briefing half is unchanged.
v2 adds the recording half in `writing-plans`, because a list
reconstructed from memory at finish time is not a record.

**Target:** `skills/finishing-a-branch/SKILL.md`, Step 0 (Review
Gate), build-mode dispatch instructions; and
`skills/writing-plans/SKILL.md`, execution/tracking rules.

**Edit (a)** — in `writing-plans`: the plan file carries a
`## Deviations` section, empty at approval. During execution, every
departure from the spec or plan is appended at the moment it is made:
what changed, and the implementer's rationale. A deviation that is
not logged when made does not exist at review time.

**Edit (b)** — in `finishing-a-branch`, add to the material passed to
the `code-reviewer` agent:

> The plan's `## Deviations` list: every known deviation from the
> spec, each with the implementer's rationale, framed as a question
> for the reviewer to judge — not a fact to accept.

**Rationale:** In the source project, one deliberate deviation passed
to the reviewer this way produced the run's best finding: the
reviewer confirmed the deviating behavior was correct and refuted the
implementer's recorded rationale for it, which was then corrected in
the spec. Deviations hidden from the reviewer get either missed or
blindly flagged; deviations presented as settled get rubber-stamped.
The v2 addition closes the gap the v1 edit silently depended on:
without observation-time logging, the briefing list is a
recollection, and recollections omit exactly the deviations that
matter.

---

## Change 6 — designing-tasks: build-mode specs carry a flow sketch

**Status vs v1:** amended. One fix: the depth budget gets a fallback,
because chimera cannot assume every project defines one.

**Target:** `skills/designing-tasks/SKILL.md`, the "Mode Fork"
section, build-mode task spec bullet list; also checklist item 7
(Self-review).

**Edit:** Add one required spec element for build tasks that add or
reshape modules:

> - Flow sketch: a short diagram that traces one input through the
>   named functions and files to the output. If tracing one call
>   crosses more than the depth budget, the spec says so and
>   justifies each hop — or the design flattens before it is
>   presented. The depth budget comes from the project's coding
>   rules; if the project defines none, the budget is two files per
>   traced call.

Extend Self-review (item 7): re-walk the flow sketch and count the
files per traced call.

**Rationale:** In the source project, an extraction module's spec
listed its structure as a table of seven files. The human partner
approved the table, the module was built, reviewed, and merged — and
the partner then read the code, found that tracing one extraction
crossed four files, and drove a post-merge restructuring down to
three files plus two further reshapes (a request object deleted, two
processing lanes decoupled). The artifact that finally communicated
the structure was a call-flow diagram, added to a module docstring
after the restructuring. A file table hides call depth; the human
approves a reading experience, and only a flow sketch shows one. The
depth-budget rule the restructuring enforced existed in that
project's coding rules; the spec format gave the approver no way to
apply it — and the v2 fallback covers projects where no such rule
exists at all.

---

## Change 7 — designing-tasks: heuristics in correctness paths are asked, not recorded

**Status vs v1:** unchanged.

**Target:** `skills/designing-tasks/SKILL.md`, new section before
"Design for Isolation"; also the Common Rationalizations table.

**Edit:** Add:

> ## Decisions That Are the Human's Call
>
> A Decisions section records judgment calls — but recording is not
> consent. Some decisions must be asked as an explicit question
> (checklist item 3) before the spec is written, never only recorded:
>
> - Any heuristic placed in a correctness path: a fail-closed gate, a
>   value-deciding rule, an acceptance fallback. The human chooses
>   between the heuristic and the honest alternative (narrower scope,
>   an exemption, a loud failure) knowing the trade-off.
> - Any renegotiation of a requirement's stated scope.
>
> Litmus: if a reviewer could plausibly say "this cleverness does not
> belong in a correctness path," the human decides at design time.

Rationalizations table, add:

| "The Decisions section records it, that's enough" | Recording is not consent. A heuristic in a correctness path is asked as a question, not filed. |

**Rationale:** In the source project, a validator's fabrication gate
(reject any extracted identifier absent from the email's text) needed
an escape for invoice ranges: emails write `INV # J1768-J1779`, the
extractor expands the range, and interior members never appear
literally. The spec resolved this with a range-detection heuristic
(accept a value bracketed by two adjacent same-shaped identifiers)
recorded as a Decisions entry — no question asked. The heuristic was
built, a reviewer found a bypass (unrelated same-width numbers
forming a fake range), the heuristic was tightened, and the human
partner — engaging with it for the first time while reading the
merged-candidate code — removed it entirely in favor of exempting
invoices from the gate, with the requirement's scope amended. Built,
tightened, and deleted inside one day. The same task's other gate
decision (strict cited-layer search versus any-layer search) was
asked as an explicit question at design time, decided once, and never
relitigated. Decisions surfaced as questions stick; decisions filed
in spec sections get discovered late and reversed at triple cost.

---

## Change 8 — /design-project: insert a BIND phase (Phase 1b) before PRD approval

**Status vs v1:** restructured. v1 proposed a
"persistent-model-discovery" phase built around six persistence
questions. v2 widens the phase: it locks **all** commitments the
evidence imposes — format requirements and scope boundaries as well
as the persistent model — because the source project's decisive
genesis artifacts included commitments that no persistence
questionnaire would have produced. The persistence checklist survives
intact as the mandatory core when its trigger conditions hold. v2
also fixes the ordering note, resolves the TRD-versus-ADR relation,
and drops the shallow-TRD file for untriggered projects.

**Target:** `commands/design-project.md` (new Phase 1b between the
data-contact spike and PRD writing); new file
`skills/persistent-model-discovery/SKILL.md`; `templates/prd-app.md`;
`templates/prd-ml.md`; `templates/system-design.md`.

### Edit (a) — Phase 1b: BIND, in `/design-project`

Insert after Phase 1 (DISCOVER) and the data-contact spike
(Change 2), before the PRD is written:

> ## Phase 1b — BIND
>
> Convert the evidence into commitments. Take the constraints from
> the data-contact spike's closure section and the business intent
> from the Phase 1 brainstorm. For each commitment, write one entry:
>
> **evidence → constraint → implications for the next phase.**
>
> Commitments come in three kinds:
>
> 1. **Format and input requirements.** What submissions the system
>    accepts; what is out and handled by explicit workaround instead
>    of system complexity.
> 2. **Scope boundaries.** Which subset of the observed variation the
>    pilot commits to supporting; what is deferred, with its trigger.
> 3. **The persistent model** — when the trigger below fires, invoke
>    `chimera:persistent-model-discovery` and produce
>    `docs/technical-requirements.md`.
>
> An entry whose implications name no design consequence is a
> finding, not a commitment; it stays in the spike report.
>
> **Approval gate:** your human partner approves the commitments
> before the PRD is written. The PRD then cites them; it does not
> re-litigate them.

**Ordering note (required in the command text):** Phase 1b needs two
inputs that must exist first — the spike's evidence and the
brainstorm's answer to "who is this for and who consumes the
output." Consumer discovery is conversation, not profiling; it
happens in Phase 1. Phase 1b precedes PRD *writing*, not the
discovery dialogue. Sequence: brainstorm → data-contact spike →
BIND → PRD.

### Edit (b) — new skill `persistent-model-discovery`

Trigger (conditional): invoke when the system has ANY of:

- External consumers (API, database, data feed others depend on).
- Reproducibility needs (ML, experiments, audit trail).
- Schema migration costs (expensive to change post-ship).
- Compliance needs (audit trail, data retention, regulatory).
- AI systems with training-data versioning, model provenance, or
  reproducibility requirements.

Six required questions (checklist; one todo each):

1. Grain: what is one row in the primary table?
2. Immutability: what never changes, and why?
3. Corrections: when values must change, what is the mechanism —
   mutation, versioning, append-only, or frozen?
4. Consumers: who queries this data, and what questions must be
   answerable — including months later?
5. Scope boundaries: what is in scope, what is out, why?
6. Failure modes: what makes this system wrong if the immutability
   discipline is skipped?

Deliverable when triggered: `docs/technical-requirements.md` (TRD)
answering:

1. What is the persistent model? (ER sketch, grain, primary keys.)
2. What is the immutability policy? (What never changes, why, where.)
3. What is the correction policy?
4. Who are the downstream consumers, and what history must they see?
5. What are known constraints? (From profiling, feasibility,
   compliance — cite the BIND entries.)
6. What are the failure modes if the discipline is skipped?

Human approval of the TRD is required before PRD writing.

**When NOT triggered:** no file. Write one line in the PRD
("Persistence: mutable state, single user, resets acceptable") and
proceed. *(v1 → v2: v1 required a shallow TRD file stating the same
sentence. A document whose entire content is one sentence is
ceremony; chimera's stance is opt-in discipline, strict once
entered — not artifacts recording that discipline was not needed.)*

**Relation to ADRs (v1 → v2, new):** the persistent model is one
interlocking design — grain, immutability, corrections, and
consumers cannot be approved as separate decisions — so it gets one
artifact, the TRD. To keep the ADR index complete, Phase 2 records a
one-line Tier-1 ADR: "Persistent model per
`docs/technical-requirements.md`; reversal cost: schema migration
with data backfill." One home for the design, one pointer in the
decision index; never two competing homes.

### Edit (c) — templates

- `templates/prd-app.md` and `templates/prd-ml.md`: add required
  section "Commitments realized: [reference to the Phase 1b entries
  and, when present, `docs/technical-requirements.md`]".
- `templates/system-design.md`: add preamble line "This design
  realizes [grain], enforces [immutability policy], and supports
  [downstream consumers] per `docs/technical-requirements.md`" —
  delete the line when no TRD exists.

### Why the phase widened (v1 → v2)

In the source project, the genesis-grade commitments were of three
kinds, and only one is a persistence question. (1) A format-only
input requirement (observed: 23 of 25 pilot files were PDF; 2 were
XLSX/DOCX) with implications: the parser assumes the 3-file
reference structure; the schema does not handle format conversion;
blocked suppliers get explicit manual workarounds, not system
complexity. (2) A scope boundary: a supplier tier classification
deciding who is in the pilot and on what terms. (3) The persistent
model: a 7-table schema with immutable sources, immutable extraction
outputs, append-only corrections, and dual status fields (technical
run state ≠ business state). v1's six questions would have produced
(3) and missed (1) and (2). The pattern all three share is
evidence → binding constraint → implications; the phase is named for
the pattern, and the persistence questionnaire is its most expensive
special case.

### Note — a deliberate partial reversal of a recorded rejection

Chimera's BMAD trawl
(`docs/research/2026-08-03-prd-trawl-bmad.md`, §3) rejected "length
scales with stakes": templates stay one-size at full rigor. Change
8's conditional trigger — full TRD when consumers, audit trail, or
migration cost fire; one PRD line otherwise — is a form of stakes
calibration, and this plan says so rather than drifting silently.
The distinction that keeps the original rejection intact: BMAD
scales *rigor* (a dial over how carefully any document is written);
the trigger scales *scope* (a binary, evidence-based test of whether
a whole artifact applies at all). Documents that exist are still
written at full rigor. Record this distinction in the trawl doc as
an amendment, the way the Glossary reversal was recorded in its §6.

**Rationale (core, from v1):** In the source project, the business
requirement "extract shipment records from emails" seemed simple at
PRD time. During implementation, the human partner drove a full
rework of the schema by working backward from downstream
consumption: "what does a database consumer querying this six months
from now need to trust?" That question revealed the 7-table schema
described above. None of it appeared in the original PRD; the schema
was discovered mid-implementation, and the design documents now lead
the shipped code by a full rework. If the persistent model had been
locked before PRD writing, the schema would have been designed at
genesis. Change 2 profiles what evidence exists; Change 8 converts
evidence and business intent into locked commitments. Both gates are
necessary and sequential.

---

## Change 9 — exploring-reproducibly: findings close as constraints, not verdicts

**Status vs v1:** new. This installs the organizing principle at task
altitude, so it applies to every evidence task, not only genesis.

**Target:** `skills/exploring-reproducibly/SKILL.md`, the findings-doc
closing contract; `agents/code-reviewer.md`, the exploration-mode
rubric.

**Edit (a)** — in `exploring-reproducibly`, extend the closing
contract. Today the findings doc closes with:

```
Decision: <adopt | reject | park> because <numbers>
```

Extend it: every **adopt** decision must carry its consequence chain —

```
Decision: adopt <what> because <numbers>
Constraint: <what we now commit to>
Implications: <the design or process consequences, named — or
  "no design consequence">
```

`reject` and `park` keep the one-line form. A findings doc whose
adopt decision names no constraint and no implications is incomplete.

**Edit (b)** — in `agents/code-reviewer.md`, exploration rubric,
extend the existing decision-line check:

> - **Decision line (IMPORTANT):** findings doc must end with
>   `Decision: <adopt|reject|park> because <numbers>`; an adopt
>   decision must also carry `Constraint:` and `Implications:` lines
>   (or an explicit "no design consequence").

**Rationale:** The decision line already existed and was enforced,
and the source project still produced two evidence documents that
were "information without implications": findings and verdicts, but
no commitments the next phase could design against. The third
version added no new evidence — it reframed the same evidence into
binding constraints with named implications, and only that version
unblocked design. A verdict says what the evidence showed; a
constraint says what we now build differently because of it. The
adopt branch is where the gap lives: adopting a finding without
naming its implications is how "interesting findings limbo" happens.
This change is deliberately small — two lines in a closing contract
and one rubric line — because the failure was not missing machinery
but a machine that stopped one step too early.

---

## Change 10 — pressure-test the v2 skill edits against their own failure stories

**Status vs v1:** new. Adopted from Superpowers' `writing-skills`
discipline ("no skill without a failing test — if you didn't watch
an agent fail without the skill, you don't know if the skill teaches
the right thing"), which chimera never lifted. See
`docs/research/2026-07-29-superpowers-deep-dive.md`, §(a).14 and
§(g).

**Target:** new files `docs/testing/pressure-scenarios/<change>.md`
in the chimera repository; plus one step in this plan's
implementation order (below).

**Edit:** Before a group lands, write one pressure-scenario file per
change in that group, derived from the change's own rationale — the
observed failure is already documented, so the expensive part of
Superpowers' method (watching the failure happen) is already paid.
Each scenario file states:

1. **The setup:** the situation from the rationale, generalized off
   the source project (e.g. for Change 7: "a fail-closed gate needs
   an escape; a heuristic resolves it; the spec is being drafted
   under time pressure with the design dialogue already long").
2. **The failure to reproduce:** what the agent did without the
   edit (filed the heuristic as a Decisions entry; never asked).
3. **The pass condition:** the observable behavior the edited skill
   must produce (the heuristic is asked as an explicit question
   before the spec is written).
4. **Pressure:** at least two stacked pressures from the Superpowers
   catalog (time, sunk cost, authority, exhaustion, social), because
   unpressured compliance does not predict pressured compliance.

Check each edited skill against its scenarios by walking the
scenario with the skill loaded; a full LLM-actor eval harness is not
required at this scale. A scenario the edit does not pass sends the
edit back before the group lands.

Additionally, record in each scenario file which failure form the
edit uses, per Superpowers' measured Match-the-Form-to-the-Failure
doctrine — discipline failure → prohibition + rationalization table
(Change 7); omitted element → required template slot (Changes 1, 5,
6, 9); wrong-shaped output → positive recipe (Change 2's report
contract). The v2 edits already comply; recording the mapping keeps
future edits deliberate.

**Rationale:** Every v2 change carries an observed-failure rationale,
which makes chimera unusually well-positioned to adopt the one
Superpowers practice it skipped: the failure stories are ready-made
test scenarios. Without this step, the plan lands eight plausible
skill texts; with it, each text is checked against the exact
situation it exists to prevent. Superpowers' own creation log
documents why this matters: its TDD skill took six
red-green-refactor iterations against observed rationalizations
before it held.

---

## Change 11 — /design-project: genesis cross-reference checklist

**Status vs v1:** new. Adopted in reduced form from BMAD's
PRD validation checklist (a seven-dimension rubric run by a reviewer
subagent), of which chimera previously took only a four-point
self-check. See `docs/research/2026-08-03-prd-trawl-bmad.md`, §2–3.

**Target:** `commands/design-project.md` — the self-check lists in
Phases 1b, 1c, 2, and 3.

**Edit:** Add reference-integrity lines to the existing self-checks
(fix inline, no re-review — the established pattern):

- Phase 1b (BIND): every commitment traces to a spike finding or a
  brainstorm statement; every violator of a format/scope commitment
  has a disposition; the TRD, when present, cites the BIND entries
  it realizes.
- Phase 1c (PRD): every commitment the PRD's "Commitments realized"
  section cites exists in Phase 1b's output; no FR contradicts a
  commitment; FR IDs unique and contiguous (existing check,
  restated here as part of the same pass).
- Phase 2 (ARCHITECTURE): when a TRD exists, the one-line Tier-1
  ADR pointing at it exists; every deferral carries its trigger
  (existing check).
- Phase 3 (SYSTEM DESIGN): the preamble's grain, immutability
  policy, and consumers match the TRD verbatim; every module name
  matches the PRD Terms table (existing check).

**Rationale:** v2 grows genesis from four artifacts to roughly seven
(spike report, brief, commitments, TRD, PRD, ADRs, system design)
with load-bearing cross-references between them. Cross-reference
drift is now a real failure surface, and it is exactly the failure
the source project exhibited: design documents that lead the shipped
code, and requirement labels that stop matching behavior. BMAD's
answer is a reviewer subagent; chimera's cheaper equivalent is
extending the self-check pattern the command already uses — the
human approval gate remains the review.

---

## Change 12 — /retrospect: formalize the loop that produced this plan

**Status vs v1:** new. Adopted from the shape of ECC's `/learn-eval`
(manual, quality-gated, placement-aware extraction), which chimera's
own trawl marked "the keeper for chimera v1.x" and never landed. See
`docs/research/2026-07-29-ecc-learning-hooks.md`, §(a). Retargeted:
ECC extracts learned code patterns; chimera's version extracts
process amendments.

**Target:** new file `commands/retrospect.md`; one routing row in
`skills/using-chimera/SKILL.md`.

**Edit (a)** — the command. Invoked after significant field use of
chimera (a project phase completed, a run of tasks through the
loop), or when the human partner asks for a retrospective:

> ## /retrospect
>
> Produce a chimera improvement spec from field experience. The
> output format is the one this plan uses: per change — target
> file, the edit, a self-contained rationale citing the observed
> event inline.
>
> 1. **Collect candidates.** Walk the project's history for
>    friction events: post-merge corrections, improvised ceremony,
>    decisions relitigated after implementation, interrupts where
>    the human forced a step chimera did not prescribe, skills that
>    were wrong or silent when needed.
> 2. **Quality-gate each candidate** (the /learn-eval gate,
>    retargeted — actually read the files):
>    - Observed, not invented: the rationale must cite a real event.
>      A hypothetical failure is not a candidate.
>    - Reusable, not one-off: would this bite a different project?
>      Project-specific lessons go to the project's CLAUDE.md or
>      memory, not the plugin.
>    - Overlap check: grep the chimera skills and commands for
>      existing coverage; prefer amending an existing skill over
>      creating a new one.
>    - Form check: match the edit's form to the failure type
>      (prohibition + rationalization row / required template slot /
>      positive recipe / routing row).
> 3. **Verdict per candidate:** Adopt / Improve then adopt / Absorb
>    into an existing change / Drop. Dropped candidates are listed
>    with one line of reasoning — a dropped lesson re-surfaces
>    otherwise.
> 4. **Write the spec** to `docs/chimera-improvements-<date>.md` in
>    the consuming project, in STE register, self-contained for an
>    agent with no project context. Present it for the human
>    partner's review; the plugin edit itself is a separate,
>    approved task in the chimera repository.
>
> The command never edits the plugin directly, and never runs
> automatically — retrospection is invoked, not hooked. (The
> automated alternative was evaluated and rejected: ECC's
> instinct-based v2 took five issue-numbered production incidents
> to stabilize.)

**Edit (b)** — routing row in `using-chimera`:

| Situation | Invoke |
|---|---|
| Retrospective on how chimera itself performed; turning project friction into plugin improvements | `/retrospect` |

**Rationale:** The workflow that produced this plan — field use →
retrospective → quality-gated improvement spec → plugin changes —
is chimera's learning loop, executed by hand twice (the v1 spec and
this document). It currently depends on the operator remembering to
run it and improvising its format each time. ECC's `/learn-eval` is
the closest existing formalization: extraction with a mandatory
quality gate (overlap grep, absorb-vs-create, placement) and a
holistic verdict instead of a numeric rubric. Retargeting it from
learned snippets to process amendments makes the loop repeatable,
and the required observed-event rationale is what feeds Change 10
its pressure scenarios.

---

## Change 13 — a living process map in the chimera repo

**Status vs v1:** new. Requested by the maintainer so the current
shape of the whole process is always checkable at a glance, instead
of living only in skill bodies and in this plan.

**Target:** new file `docs/process-map.md` in the chimera
repository; one line in the chimera repo's `CLAUDE.md`.

**Edit (a)** — create `docs/process-map.md` with the content below.
The `(Ch. N)` annotations mark which v2 change introduced an element;
they stay until the next major version, then get pruned.

**Edit (b)** — add to chimera's `CLAUDE.md` contributor rules:

> `docs/process-map.md` is the living process map. Any commit that
> alters a flow — a phase, a gate, a routing row, a skill's terminal
> state — updates the map in the same commit. A map that no longer
> matches the skills is treated the same as a stale requirement
> label.

**Map content:**

```markdown
# Chimera process map

> The current shape of the whole loop. Updated in the same commit as
> any change that alters a flow. (Ch. N) marks the v2 change that
> introduced an element.

## 1. Project genesis — /design-project

Phase 0  TYPE             project type; existing repo?; brainstorm/distill
Phase 1  DISCOVER         brainstorm: problem, users, consumers
   ↓
Phase 1a DATA-CONTACT SPIKE   (Ch. 2) fires when a real corpus or
   artifact format exists:
   pin samples → name the priority authority doc →
   dispatch corpus-profiler (mechanical profile + handoff
   sections; judgment returned as questions) →
   close decision-blocking evidence gaps →
   human + main agent write the decision brief per the
   "profile → brief" recipe in writing-comparative-reports
   (population join, constraint move, reference implementation,
   bidirectional grounding, live conflicts, evidence labels)
   ↓
Phase 1b BIND             (Ch. 8) convert evidence into commitments,
   each as evidence → constraint → implications:
   • format/input requirements   • scope boundaries
   • persistent model — if external consumers / audit trail /
     migration-cost triggers fire → persistent-model-discovery
     skill → docs/technical-requirements.md → human approval
     (untriggered: one line in the PRD, no file)
   self-check: commitments trace to evidence; violators have
   dispositions (Ch. 11)
   ↓
Phase 1c PRD              written against brief + commitments;
                          cites them, never re-litigates them;
                          self-check: cited commitments exist,
                          FR IDs contiguous (Ch. 11)
Phase 2  ARCHITECTURE     ADRs; one-line Tier-1 ADR points at the
                          TRD when one exists (Ch. 8, 11)
Phase 3  SYSTEM DESIGN    preamble states grain / immutability /
                          consumers per the TRD, verbatim (Ch. 8, 11)
Phase 4  ROADMAP          queue of rows; gate rows; Realizes column
Phase 5  SCAFFOLD         skeleton; /new-project; commit genesis

## 2. Build-mode task — /start-task

designing-tasks:
  explore context → re-present FR contents for re-confirmation
    (Ch. 1)
  clarifying questions → correctness-path heuristics and scope
    renegotiations are ASKED, never only recorded (Ch. 7)
  spec carries: Decisions section (Ch. 1) + flow sketch against the
    depth budget (Ch. 6)
  STE register; notation defined at first use (Ch. 3)
   ↓
writing-plans:
  plan carries an empty ## Deviations section (Ch. 5)
   ↓
test-driven-development (execution):
  deviations logged in ## Deviations at the moment they are made
    (Ch. 5)
   ↓
verifying-before-done
   ↓
finishing-a-branch:
  code-reviewer briefed with spec + plan constraints + the
    deviations list framed as questions (Ch. 5)
  → green suite → menu (merge / PR / keep)

## 3. Exploration-mode task — /start-task

designing-tasks → research brief with decision line
   ↓
exploring-reproducibly:
  pin snapshot → eda-profiler (one tabular dataset) or
  corpus-profiler (heterogeneous corpus) (Ch. 2)
  findings doc closes with Decision + Constraint + Implications on
  every adopt, or "no design consequence" (Ch. 9)
   ↓
code-reviewer (exploration rubric, checks the closure) (Ch. 9)
   ↓
finishing-a-branch: findings merge; experiment code archived

## 4. After the loop closes

Small behavior change to already-merged work
   → Amendment path in finishing-a-branch (Ch. 4), routed from
     using-chimera: no spec, no plan; tests move with the change;
     every doc stating the amended behavior moves in the same commit

## 5. The learning loop (chimera improving chimera)

Field use accumulates friction
   → /retrospect (Ch. 12): collect friction events → quality-gate
     (observed, reusable, overlap grep, form check) → verdicts →
     improvement spec in docs/
   → implement in the chimera repo: each change pressure-tested
     against its own failure story before landing (Ch. 10)
   → this map updated in the same commit as any flow change (Ch. 13)
```

**Rationale:** After v2 the process spans three commands, ten
skills, and three agents; its shape exists nowhere as one artifact
except inside this plan, which is a migration document, not a home.
The map gives the maintainer one place to check what the process
currently is, and the same-commit rule keeps it honest — the same
principle the amendment path (Ch. 4) applies to project docs.

---

## No change needed (observations that validate current design)

- The `code-reviewer` gate found genuine defects on every task it
  reviewed (silently dropped content, a dict collapsing duplicate
  keys, a default that turned an omitted field into a silent pass,
  two measurement blind spots). Keep it exactly as designed.
- Design iteration during first data contact is the design absorbing
  facts, not churn; Change 2 fixes the ordering, not the iteration.
- Plan files plus git as re-entry state survived context compaction
  twice with no lost steps. Keep as is.
- `eda-profiler` keeps its narrow mechanical contract untouched
  apart from one dispatch note pointing non-tabular corpora at
  `corpus-profiler` (v2 explicitly reverses v1's plan to extend it —
  see Change 2).

### Parent-repo comparison outcomes (checked against the trawls)

Changes 10–12 are the only adoptions the parent repos
(Superpowers, BMAD, ECC) still owe chimera after v2. The rest of the
comparison confirms standing verdicts:

- **Superpowers SDD stays rejected.** Change 5 (deviations logged at
  the moment, briefed as questions) is the solo-scale form of SDD's
  review package and "implementer rationales are claims" stance; the
  full machinery (ledger, five-round fix loops, per-role models)
  remains team-scale. SDD stays the reference if orchestration ever
  enters.
- **Enforcement stays procedural (tier 2).** All v2 changes are
  required artifacts and template slots whose violations leave
  visible gaps. The one tier-3 (hook-enforced) candidate remains the
  standing PreToolUse TDD gate from the ECC analysis, unchanged by
  this plan. Change 5's residual weakness — an unlogged deviation is
  a semantic fact no hook can detect — is accepted, not fixable by
  enforcement tier.
- **Already-absorbed inventory** (do not re-adopt): ECC's
  code-reviewer, Pattern Grounding, 3-attempt breaker, branch
  decision table; BMAD's FR IDs, Done-when lines, `[ASSUMPTION]`
  tags, guard metric, Terms table; Superpowers' brainstorming / TDD
  / finishing / worktree spine and enforcement-technique vocabulary.
- **What no parent has:** evidence-closure (Change 9), corpus
  profiling with a narrative recipe (Change 2), the BIND phase and
  persistent-model discovery (Change 8), the STE register, and the
  exploration/ML mode. On these, convergence runs from the parents
  toward chimera, not the reverse.

---

## Implementation order

Grouped so each lands as one coherent commit in the chimera repo;
later groups reference earlier ones.

1. **Group A — small, independent, no cross-references:**
   Change 3 (writing-in-ste), Change 6 (flow sketch), and Change 13
   (create `docs/process-map.md` first, showing the target state —
   later groups then land against a map that already names them,
   and the same-commit rule applies from here on).
2. **Group B — the decisions pair (land together):**
   Change 1 + Change 7 (designing-tasks).
3. **Group C — the deviations chain:**
   Change 5 (writing-plans log, then finishing-a-branch briefing).
4. **Group D — amendment path:**
   Change 4 (finishing-a-branch + using-chimera routing row).
5. **Group E — evidence closure rule:**
   Change 9 (exploring-reproducibly + code-reviewer). Land before
   Group F, because Changes 2 and 8 cite the rule.
6. **Group F — genesis gates (land together):**
   Change 2 (spike + writing-comparative-reports skill +
   corpus-profiler agent + eda-profiler dispatch note + routing row),
   Change 8 (BIND phase + persistent-model-discovery skill +
   template edits + the trawl-doc amendment from its Note), and
   Change 11 (genesis cross-reference checklist — same file as the
   Phase edits).
7. **Group G — the learning loop (independent, any time):**
   Change 12 (/retrospect command + routing row).

**Change 10 is not a group — it is a gate on every group:** before a
group lands, its pressure-scenario files are written (from the
changes' own rationales) and the edited skills are walked against
them. A failed scenario sends the edit back.

Each group: edit in `/home/leoqi/dev/chimera` on a branch, run the
plugin's smoke checks (`docs/testing/smoke.md`) plus the group's
Change-10 scenarios, commit with conventional-commit messages.
Version bump and CHANGELOG entry after Group G.
