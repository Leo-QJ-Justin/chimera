# {{PROJECT_NAME}} — System Design

> Modules and their contracts. The loop designs features *within* these
> boundaries; changing a boundary is a genesis-level decision (new ADR).

## Module table

| Module | Responsibility | Inputs | Outputs | Depends on |
|--------|----------------|--------|---------|------------|
| {{name}} | {{one clear purpose}} | {{exact types/shapes}} | {{exact types/shapes}} | {{modules}} |

## Data flow

{{Arrow sketch, e.g.: ingest → validate → features → train/serve → report.
Note where exploration (notebooks) reads from vs what production writes.}}

## Repo layout

{{Where things live: pipeline code vs notebooks/ vs docs/ vs tests/.}}

## Open questions

{{Unresolved items — each should become an ADR or an exploration task.}}
