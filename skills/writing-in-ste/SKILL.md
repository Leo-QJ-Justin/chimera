---
name: writing-in-ste
description: Use when writing or reviewing a PRD, ADR, spec, tool description, error message, or instruction that must be understood without follow-up questions
---

# Writing in STE

## Overview

**Core principle:** write for a reader who cannot ask you what you meant.

Use ASD-STE100's agent-facing principles: one meaning per word and one
structure per sentence. Its approved-word dictionary is outside this skill.

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
| Notation at first use | Give every symbol, formula variable, or abbreviation a plain-word reading where it first appears: "$P \setminus G$ (the pilot set excluding the gold set)" | Use undefined notation — a document that must be parsed without a follow-up question fails the moment it does |

The PRD `## Terms` table is the project dictionary that keeps domain nouns
stable across documents.

## Process

1. Read the whole text once for meaning. Do not rewrite before you know
   what it must still say.
2. Walk it sentence by sentence. Flag each rule violation.
3. Flag every symbol, formula variable, or abbreviation that has no
   plain-word reading at its first appearance.
4. Rewrite each flagged sentence. Keep the meaning exactly.
5. If a rewrite would drop a number, a scope qualifier, or a safety
   condition, keep the longer sentence and flag the trade-off. Precision
   outranks brevity.
6. Report the before/after table. If the text already complies, say so.
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

Each genesis document declares the register:

```markdown
> Written in Simplified Technical English (ASD-STE100 register): short
> sentences, active voice, simple tenses, one meaning per term. Terms are
> defined in the Terms table.
```

Run the rewrite before approval; a later rewrite was not approved.

## Common mistakes

| Mistake | Why it fails |
|---|---|
| Simplifying a threshold away | "fails above roughly 1.0" is not "fails above 1.0". Numbers are precision, not verbosity |
| Splitting a sentence that carried a dependency | Two short sentences can lose the "only if" between them. Keep the condition explicit |
| Treating STE as a word-count target | A 12-word ambiguous sentence is worse than a 22-word exact one |
| Rewriting quoted material | Quotes, log output, and error strings are evidence. They stay verbatim |
| Applying it to the whole repo | Genesis documents, specs, and agent-facing strings only |
