# Documentation

## Docstrings

Google style. Summary line, blank line, then one to four plain sentences
of rationale only where the choice is non-obvious. Document Args,
Returns and Raises where they apply and nowhere else. Never restate a
type the signature already gives.

Module docstrings stay under 15 lines: what lives here, what does not.

## Comments

- State the reason, at the decision point. `clipped at 1.0 because the
  solver diverges above it` earns its line.
- Never narrate the code. A comment that repeats the statement below it
  is deleted.
- Never cite a document that does not ship with the code. No design doc
  titles, ticket numbers, or planning references in source.

## Register

Professional library voice: keep the rationale, drop the rhetoric. No
selling, no superlatives, no history of how the code came to be.

## Extension points

Every extension point names one home: where a new metric, plot, family,
or unit goes, and which contract it must satisfy. If a reader cannot
find that home from the docs, the docs are incomplete.

- [ ] Public callables have a summary line, plus rationale where the
      choice is non-obvious.
- [ ] No comment restates its code or cites a non-shipping document.
- [ ] Each extension point documents its one home.
