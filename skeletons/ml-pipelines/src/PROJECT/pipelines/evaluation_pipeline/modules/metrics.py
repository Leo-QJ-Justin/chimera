"""The project's metric definitions - one home, four consumers.

The training pipeline scores its splits, the trainers implement
``evaluate`` and the evaluation pipeline writes its report all through
these functions. The import direction (training -> evaluation) looks
backwards for a moment and is deliberate: metrics belong to the pipeline
that *reports* them, and a second definition beside the trainer is how a
project ends up with a val F1 that disagrees with its report's F1.

Add a metric here and it flows into ``best.json``, the tracker, and the
evaluation report at once. Add it inline in a pipeline and it does not.

Logging convention (D12): scalars go through the logger; the
pre-formatted ``classification_report`` block goes through ``print``,
because a per-line level prefix mangles an aligned table.
"""

import logging
from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn import metrics as sk_metrics
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    make_scorer,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

logger = logging.getLogger(__name__)

CLASSIFICATION_METRICS = ("accuracy", "f1_macro")
REGRESSION_METRICS = ("rmse", "mae", "r2")

# The project's metric aliases: short names with their arguments already
# decided. ``f1_macro`` is the reason this table exists - sklearn exposes
# ``f1_score``, and whether it is macro- or weighted-averaged is a project
# decision that must not be re-made at each call site.
METRIC_FUNCTIONS: dict[str, Callable] = {
    "accuracy": accuracy_score,
    "f1_macro": lambda y_true, y_pred: f1_score(
        y_true, y_pred, average="macro", zero_division=0
    ),
    "rmse": lambda y_true, y_pred: np.sqrt(mean_squared_error(y_true, y_pred)),
    "mae": mean_absolute_error,
    "r2": r2_score,
}


def default_metrics(task: str) -> list[str]:
    """The metric names a task reports when the caller names none."""
    names = REGRESSION_METRICS if task == "regression" else CLASSIFICATION_METRICS
    return list(names)


def resolve_metric(metric: str | Callable) -> tuple[str, Callable]:
    """Turn a metric name or callable into ``(name, function)``.

    Resolution order: the project's aliases above, then any function in
    ``sklearn.metrics`` by its exact name, then a caller-supplied
    callable. Project aliases win so that ``"f1_macro"`` never silently
    becomes something else, and so a report and a ``best.json`` computed
    months apart still mean the same thing.

    Raises:
        ValueError: On a name that resolves nowhere, listing the aliases.
    """
    if callable(metric):
        return getattr(metric, "__name__", "custom_metric"), metric
    if metric in METRIC_FUNCTIONS:
        return metric, METRIC_FUNCTIONS[metric]
    sklearn_fn = getattr(sk_metrics, metric, None)
    if callable(sklearn_fn):
        return metric, sklearn_fn
    raise ValueError(
        f"Unknown metric {metric!r}: not a project alias {sorted(METRIC_FUNCTIONS)} "
        "and not a function in sklearn.metrics"
    )


def compute_metrics(
    y_true, y_pred, task: str = "classification", metrics: list | None = None
) -> dict[str, float]:
    """The project's metric dict for a task.

    Args:
        y_true: Ground truth.
        y_pred: Hard predictions (class labels, or values for regression).
        task: ``"classification"`` or ``"regression"``; picks the defaults.
        metrics: Metric names or callables. None -> the task defaults, whose
            keys match ``schemas.metric_names(task)``.

    Returns:
        Metric name -> value.
    """
    results = {}
    for metric in metrics or default_metrics(task):
        name, function = resolve_metric(metric)
        results[name] = float(function(y_true, y_pred))
    return results


def cv_scoring(metric: str | Callable) -> dict[str, Callable]:
    """One project metric as a sklearn scoring mapping.

    The bridge for sklearn's own machinery - ``sklearn.cross_validate``,
    ``GridSearchCV``, the base trainer's Optuna objective - which scores
    through the scorer protocol rather than through :func:`compute_metrics`,
    so a project alias has to be *wrapped* rather than named. Naming it
    would be wrong twice: ``"rmse"`` is not a sklearn scoring string at all
    (it is ``neg_root_mean_squared_error``), and reaching for sklearn's own
    string would re-decide what the alias means - which is precisely what
    this module exists to prevent.

    ``BaseTrainer.cross_validate`` needs no scorer: it runs the family's own
    procedure per fold and scores the fold through :func:`compute_metrics`
    directly, so it takes metric *names*. Either way the measurement behind
    ``best.json`` is the one the evaluation report prints.

    Args:
        metric: A project metric name (or callable), as ``selection.metric``.

    Returns:
        ``{name: scorer}``, for any sklearn API that takes ``scoring=``.

    Note:
        ``greater_is_better=True`` is not a claim about the metric; it only
        tells ``make_scorer`` to leave the sign alone, so the fold mean *is*
        the metric and ``selection.mode`` stays the one place direction is
        declared.
    """
    name, function = resolve_metric(metric)
    return {name: make_scorer(function, greater_is_better=True)}


def per_class_table(y_true, y_pred) -> pd.DataFrame:
    """Per-class precision/recall/f1/support as a frame.

    The breakdown the scalar metric dict flattens away: a macro F1 of 0.62
    is a very different story when one class has a support of 9.
    """
    report = classification_report(y_true, y_pred, zero_division=0, output_dict=True)
    rows = [
        {"class": str(label), **{k: float(v) for k, v in scores.items()}}
        for label, scores in report.items()
        if isinstance(scores, dict)
    ]
    return pd.DataFrame(rows)


def prefixed(metrics: dict[str, float], split: str) -> dict[str, float]:
    """``{"f1_macro": .8}`` -> ``{"val_f1_macro": .8}`` for flat metric stores."""
    return {f"{split}_{name}": value for name, value in metrics.items()}


def log_metrics(metrics: dict[str, float], split: str) -> None:
    """Log scalars one line each - greppable, and safe for log shipping."""
    for name, value in metrics.items():
        logger.info("%s %s: %.4f", split, name, value)


def print_classification_report(y_true, y_pred, split: str) -> None:
    """Print the per-class breakdown as its aligned text block."""
    print(f"\n=== classification report [{split}] ===")
    print(classification_report(y_true, y_pred, zero_division=0))
