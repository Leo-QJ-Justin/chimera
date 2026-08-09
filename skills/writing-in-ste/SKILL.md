---
name: writing-in-ste
description: Use when writing or reviewing a document that another party must parse without asking a follow-up question - a PRD, ADR, system design, spec, tool description, error message, or inter-agent instruction - rewrites dense or ambiguous English into one-meaning-per-word, active-voice, short-sentence form
---

# Writing in STE

> Ported from `danyuchn/asd-ste100-skill` (MIT), which repurposes
> ASD-STE100 for agent-facing English. The rule categories come from
> ASD-STE100 Issue 9 (January 2025), maintained by the Simplified
> Technical English Maintenance Group. The standard's approved-word
> dictionary is **not** reproduced here; the principle behind it is
> applied instead. For word-by-word compliance, use the free official
> download at https://www.asd-ste100.org/.

## Overview

**Core principle:** write for a reader who cannot ask you what you meant.

ASD-STE100 exists because a maintenance technician on a tarmac has no
back-channel to the author of the manual. A genesis document has the same
readers: future-you months later, an agent executing a task from it, and
a reviewer who was not in the conversation that produced it. Ambiguity
that a present author would resolve in one sentence becomes a wrong build
instead.

STE removes the two largest sources of misreading: words that carry more
than one meaning, and sentences that admit more than one structure.

## When to use

- Writing or reviewing any genesis document — PRD, ADR, system design.
- Writing a spec, research brief, or plan another session will execute.
- Writing text a machine parses without a human present: tool
  descriptions, error messages, skill bodies, inter-agent instructions.

**Do not use** on text where voice or persuasion is the point — a README
opening, a PR narrative, a commit message body. STE is deliberately flat.
Applying it there costs meaning and gains nothing.

## The rules

| Rule | Do | Not |
|---|---|---|
| One word, one meaning | Pick one verb per action and reuse it everywhere: always "check" | Rotate "check", "verify", "confirm" for the same action |
| One part of speech | "Apply oil to the bearing" (noun) | "Oil the bearing" (verb) |
| Active voice | "The trainer writes the checkpoint." | "The checkpoint is written." |
| Simple tenses | "We received the file." | "We have received the file." |
| One instruction per sentence | "Open the file. Read line 3." | "Open the file and read line 3, then check it matches." |
| Sentence length | ≤20 words for instructions, ≤25 for description | Compound sentences with stacked subordinate clauses |
| Noun clusters | ≤3 nouns: "fuel pump valve" | "high pressure fuel pump inlet valve assembly" |
| No ellipsis | Keep subject, verb, and article explicit | Drop words to save space — "files not backed up will be lost" hides which files |
| Paragraphs | One topic, ≤6 sentences | Multi-topic paragraphs |
| Lists for sequences | A numbered list for 3+ steps or conditions | A sequence buried inside one prose sentence |
| Conditions first | "If the split is temporal, sort before you cut." | "Sort before you cut, if the split is temporal." |
| Domain terms | Define each non-common-English term once, in the Terms table | Use a domain term the reader must infer |

The last row is the one that connects to the templates. STE permits a
project dictionary above its base vocabulary, which is what the PRD's
`## Terms` section is. Without that table, "one word, one meaning" has
nothing to anchor to and domain nouns drift between documents.

## Process

1. Read the whole text once for meaning. Do not rewrite before you know
   what it must still say.
2. Walk it sentence by sentence. Flag each rule violation.
3. Rewrite each flagged sentence. Keep the meaning exactly.
4. If a rewrite would drop a number, a scope qualifier, or a safety
   condition, keep the longer sentence and flag the trade-off. Precision
   outranks brevity.
5. Report the before/after table. If the text already complies, say so.
   Do not force changes onto compliant text.

## Output format

```markdown
| Rule | Before | After |
|---|---|---|
| Present perfect | "We have received the file." | "We received the file." |
| Noun cluster | "the model training run artifact directory" | "the artifact directory for a training run" |
```

Close with one line naming anything you deliberately left alone, and why.

## Applying it to genesis documents

Each genesis document opens with one line stating the register, so a
later reader knows the flatness is deliberate:

```markdown
> Written in Simplified Technical English (ASD-STE100 register): short
> sentences, active voice, simple tenses, one meaning per term. Terms are
> defined in the Terms table.
```

Run the rewrite pass before the approval gate, not after. A document
approved in one register and rewritten in another is a second document
that nobody approved.

## Common mistakes

| Mistake | Why it fails |
|---|---|
| Simplifying a threshold away | "fails above roughly 1.0" is not "fails above 1.0". Numbers are precision, not verbosity |
| Splitting a sentence that carried a dependency | Two short sentences can lose the "only if" between them. Keep the condition explicit |
| Treating STE as a word-count target | A 12-word ambiguous sentence is worse than a 22-word exact one |
| Rewriting quoted material | Quotes, log output, and error strings are evidence. They stay verbatim |
| Applying it to the whole repo | Genesis documents, specs, and agent-facing strings only |
