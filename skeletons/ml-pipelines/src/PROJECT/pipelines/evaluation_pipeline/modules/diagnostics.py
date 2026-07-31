"""Prediction-based figures for the evaluation report.

The counterpart to the training pipeline's post-fit diagnostics, split by
what each side actually needs: those need the model's internals, these need
only the joined predictions table - which is exactly why they belong here
and not there. No model is loaded, no feature is rebuilt; that is the one
data path rule (D4) holding at the plotting layer too.

Confusion matrix and residuals come from the hard predictions alone. ROC,
precision-recall and calibration need the ``proba_<label>`` columns the
inference pipeline writes when ``include_probabilities`` is on; when they
are absent the report says so rather than quietly shipping fewer figures.

Everything lands in ``<run_dir>/plots/``, which the pipeline uploads with
the rest of the run directory. Every figure is individually guarded: one
that fails costs the report a warning line, not the report.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ....core.plots import (
    plot_calibration_curve,
    plot_confusion_matrix,
    plot_pr_curves,
    plot_residuals,
    plot_roc_curves,
)

logger = logging.getLogger(__name__)

PLOTS_DIRNAME = "plots"
PROBA_PREFIX = "proba_"

CONFUSION_FILENAME = "confusion_matrix.png"
ROC_FILENAME = "roc_curves.png"
PR_FILENAME = "pr_curves.png"
CALIBRATION_FILENAME = "calibration_curve.png"
RESIDUALS_FILENAME = "residuals.png"


def write_evaluation_plots(
    run_dir, joined: pd.DataFrame, target: str, prediction_col: str, task: str
) -> tuple[list[str], dict[str, float]]:
    """Draw the figures this task supports from the joined table.

    Args:
        run_dir: The evaluation run directory; figures land in ``plots/``.
        joined: Predictions joined to ground truth.
        target: Ground-truth column.
        prediction_col: Prediction column.
        task: ``"classification"`` or ``"regression"``.

    Returns:
        ``(paths, metrics)`` - report-relative paths (``plots/<name>.png``)
        for the files that were actually written, and any scalars the
        curves produced (``roc_auc``, ``pr_auc``) for the caller to log
        alongside the report's other metrics.
    """
    plots_dir = Path(run_dir) / PLOTS_DIRNAME
    y_true = joined[target]
    y_pred = joined[prediction_col]

    written: list[Path] = []
    metrics: dict[str, float] = {}
    if task == "regression":
        written += _attempt(
            "residuals", plot_residuals, y_true, y_pred, plots_dir / RESIDUALS_FILENAME
        )
    else:
        written += _attempt(
            "confusion matrix",
            plot_confusion_matrix,
            y_true,
            y_pred,
            plots_dir / CONFUSION_FILENAME,
        )
        written += _probability_plots(joined, y_true, plots_dir, metrics)

    logger.info("Wrote %d evaluation figure(s) under %s", len(written), plots_dir)
    return [f"{PLOTS_DIRNAME}/{path.name}" for path in written], metrics


def _probability_plots(
    joined: pd.DataFrame, y_true, plots_dir: Path, metrics: dict
) -> list[Path]:
    """ROC, PR and calibration - the three that need ``proba_*`` columns."""
    columns = [c for c in joined.columns if c.startswith(PROBA_PREFIX)]
    if not columns:
        logger.info(
            "No %s* columns in the predictions file, so ROC/PR/calibration are "
            "skipped; re-run inference with include_probabilities: true to get "
            "them (the confusion matrix needs no probabilities and was drawn)",
            PROBA_PREFIX,
        )
        return []
    # Column order is the order inference wrote classes_ in, which is the
    # order the probability matrix columns mean.
    classes = [c[len(PROBA_PREFIX) :] for c in columns]
    proba = np.asarray(joined[columns], dtype=float)

    written: list[Path] = []
    written += _curve_attempt(
        "ROC",
        plot_roc_curves,
        y_true,
        proba,
        plots_dir / ROC_FILENAME,
        classes,
        metrics=metrics,
    )
    written += _curve_attempt(
        "precision-recall",
        plot_pr_curves,
        y_true,
        proba,
        plots_dir / PR_FILENAME,
        classes,
        metrics=metrics,
    )
    if len(classes) == 2:
        written += _attempt(
            "calibration",
            plot_calibration_curve,
            y_true,
            proba,
            plots_dir / CALIBRATION_FILENAME,
            classes,
        )
    else:
        logger.info(
            "%d classes; calibration is drawn for binary problems only", len(classes)
        )
    return written


def _attempt(what: str, plot, *args) -> list[Path]:
    """Draw one figure; a failure is a warning, never a failed report."""
    try:
        return [plot(*args)]
    except Exception as e:
        logger.warning("Evaluation plot %r failed (%s); the report is intact", what, e)
        return []


def _curve_attempt(what: str, plot, *args, metrics: dict) -> list[Path]:
    """As :func:`_attempt`, for the two helpers that also return AUCs."""
    try:
        path, areas = plot(*args)
    except Exception as e:
        logger.warning("Evaluation plot %r failed (%s); the report is intact", what, e)
        return []
    metrics.update(areas)
    return [path]
