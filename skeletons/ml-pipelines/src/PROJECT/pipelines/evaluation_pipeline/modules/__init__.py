"""Stateless metric and triage functions.

``metrics`` is the project's single metric definition: the trainers and
the training pipeline import it from here too, because metrics belong to
the pipeline that reports them.
"""

from .metrics import compute_metrics, default_metrics, per_class_table, resolve_metric
from .triage import error_summary, worst_cases

__all__ = [
    "compute_metrics",
    "default_metrics",
    "error_summary",
    "per_class_table",
    "resolve_metric",
    "worst_cases",
]
