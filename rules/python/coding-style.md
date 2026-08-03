---
paths: ["**/*.py", "**/*.pyi"]
---

> This file extends [common/coding-style.md](../common/coding-style.md)
> with Python specific content.

# Python coding style

## Baseline

- Google-style docstrings, per
  [common/documentation.md](../common/documentation.md).
- `ruff` clean is the bar, not a suggestion. Formatting is not a review
  topic.
- Type hints on every public signature.
- Class-body declarations that are not instance fields are `ClassVar`.

## Classes

- Declare members explicitly on each class. No mixins, no multiple
  inheritance.
- Base classes carry `@abstractmethod` contracts and shared measurement
  only.

## Config

- pydantic models are the config surface: validated data, a deliberate
  `extra` policy, defaults declared beside the fields.
- Cross-field rules are validators on the model, not checks scattered
  through callers.

## Optional dependencies

Import optional packages inside the function that needs them and raise an
error naming the extra to install.

```
try:
    import optional_pkg
except ImportError:
    raise ImportError("plotting requires: pip install <project>[plots]")
```

- [ ] ruff clean; public signatures typed.
- [ ] No mixins or multiple inheritance introduced.
- [ ] Config changes land on the pydantic model.
- [ ] Every optional dependency is lazy and names its extra.
