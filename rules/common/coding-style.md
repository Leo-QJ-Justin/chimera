# Coding style

Rules for structure and control flow, in any language.

## Depth budget

Answering "what does this code do" should take about one file. Every
layer of indirection pays rent: real added behavior, two or three
callers, or an invariant it enforces. A layer that only forwards its
arguments gets inlined.

## Duplicate horizontally, never vertically

Near-identical sibling units - peer classes, one file per family - are
acceptable and often preferred. Two mechanisms doing one job, or shared
behavior hidden up an inheritance chain, are defects. One mechanism per
concern, any number of copies across peers.

```
good:  TrainerA.fit()  TrainerB.fit()   # peers, each readable alone
bad:   BaseTrainer._fit_impl()          # one job, two places to read
       TrainerA overriding half of it
```

## Declaration over inheritance

Behavior-determining attributes and the domain-method set live in the
concrete class's own body. Base classes hold abstract contracts and
shared measurement only. Enforce it with a contract test: each declared
name must appear in the concrete class's own namespace, never inherited
from an ancestor.

## Orchestrators are sequencers

A pipeline or `run()` reads as its flow diagram: named steps in order,
no domain branches (`if kind == ...`) anywhere inside it. Plain values
cross boundaries, never config objects. Domain objects never touch
infrastructure - no trackers, no logging sinks, no file paths.

## Partition wide, not deep

One home per concern, flat and predictable. A new capability gets a
sibling file, not a new layer.

## Config is declared data

Declare defaults in code, beside what they configure. Config narrows or
disables; it does not carry behavior. Wire every knob: a switch that
changes nothing is worse than no switch at all.

## Failure sorting

- Paths that decide the correctness of numbers fail loudly. Refuse
  changed data, list the valid names when one is wrong, never guess a
  direction or substitute a default.
- Auxiliary systems - tracking, plotting, logging - warn and continue.
  A failed plot never kills a training run.
- Labels match epistemics. An estimate is not named a measurement, a
  heuristic is not named a rule, and a partial result says so.

## Before calling it done

- [ ] Every new layer has two or more callers, added behavior, or an
      enforced invariant.
- [ ] No second mechanism for a job that already has one.
- [ ] Behavior-determining attributes are declared in the concrete class.
- [ ] Orchestrators contain no domain branches.
- [ ] Every config knob is read somewhere.
- [ ] Correctness paths raise; auxiliary paths warn.
- [ ] Names claim exactly what the values are.
