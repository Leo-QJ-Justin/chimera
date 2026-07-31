"""Booster eval records -> the per-iteration history shape trainers expose.

Both boosting families record an eval curve during the fit, in the same
nested shape (``{dataset: {metric: [per-iteration values]}}``) under two
different spellings of the same idea - LightGBM through a
``record_evaluation`` callback, XGBoost through ``booster.evals_result()``
after the fit. This flattens either into ``BaseTrainer.history``.

Why that matters: the training pipeline already replays ``trainer.history``
into the tracker step-wise (and into ``metrics.jsonl``), so a family that
fills it gets per-iteration MLflow metrics and a training-curve figure for
free, with no tracking code in the trainer. Capturing here rather than in
each trainer is what stops the two families' key naming from drifting.
"""

import logging

logger = logging.getLogger(__name__)

# Substrings that mark an eval set as the training one. LightGBM names the
# training set "training" and validation sets "valid_0"; XGBoost uses
# "validation_0" for whatever it was handed first.
_TRAIN_MARKERS = ("train",)


def booster_history(evals_result: dict | None) -> list[dict]:
    """Flatten a booster's eval record into per-iteration history rows.

    Args:
        evals_result: ``{dataset_name: {metric_name: [values]}}`` as either
            booster records it. Empty or None (no eval set was given, so
            nothing was recorded) yields an empty history.

    Returns:
        One record per boosting iteration, each carrying ``epoch`` plus the
        recorded metrics prefixed by split - ``{"epoch": 0,
        "val_binary_logloss": 0.61}``. ``epoch`` is the key the pipeline's
        replay loop reads as the metric step, so boosters and the torch
        trainer are indistinguishable to it.
    """
    series: dict[str, list[float]] = {}
    for dataset, metrics in (evals_result or {}).items():
        split = "train" if _is_training_set(dataset) else "val"
        for metric, values in metrics.items():
            series[f"{split}_{metric}"] = [float(v) for v in values]
    if not series:
        return []
    # Shortest wins: a curve truncated by early stopping must not leave a
    # ragged tail of records with missing keys.
    length = min(len(values) for values in series.values())
    return [
        {"epoch": i, **{name: values[i] for name, values in series.items()}}
        for i in range(length)
    ]


def _is_training_set(dataset_name: str) -> bool:
    return any(marker in str(dataset_name).lower() for marker in _TRAIN_MARKERS)
