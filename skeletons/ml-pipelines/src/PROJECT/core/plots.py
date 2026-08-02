"""Diagnostic figures, drawn directly on matplotlib and sklearn.

Stateless helpers: each takes arrays (or a history record list), writes one
PNG, and returns the path it wrote. Nothing here reads config, touches the
tracker, or knows which pipeline called it - the run directory is uploaded
wholesale at the end of a run, so a file written into ``<run_dir>/plots/``
becomes an MLflow artifact with no tracking code of its own.

Figures are drawn directly rather than through ``mlflow.models.evaluate``,
which wants a live fluent run and a loadable model; these helpers must also
work with tracking off. Callers wrap each call in the try/except-warn
pattern the pipelines use for model logging, so a figure that could not be
drawn costs the run one warning line and never the artifacts it already
wrote.
"""

import logging
from pathlib import Path

import matplotlib
import numpy as np

# Before pyplot, not after: the backend is chosen at pyplot import time, and
# the default one needs a display that a pipeline worker does not have.
matplotlib.use("Agg")

from matplotlib import pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)

# Wide enough for a legend beside a curve, short enough to read in a PR.
_FIGSIZE = (7.0, 5.0)
_CURVE_ROW_HEIGHT = 3.0
_DPI = 120


# ------------------------------------------------------------------ curves


def plot_training_curves(history: list[dict], out: str | Path) -> Path | None:
    """Per-iteration curves from a trainer's history records.

    Series are grouped by metric rather than by split, so ``train_loss``
    and ``val_loss`` share an axes and the gap between them is visible
    without flipping between images. Series with no ``train_``/``val_``
    prefix, such as a learning rate, get an axes of their own.

    Args:
        history: Records as trainers record them, each carrying ``epoch``
            plus that iteration's metrics.
        out: Destination PNG path.

    Returns:
        The written path, or None when the history holds no numeric series
        (a family with no iterations records nothing, which is not a
        failure).
    """
    groups = _curve_groups(history)
    if not groups:
        logger.debug("History carries no plottable series; no curves written")
        return None

    steps = [record.get("epoch", i) for i, record in enumerate(history)]
    fig, axes = plt.subplots(
        len(groups),
        1,
        figsize=(_FIGSIZE[0], _CURVE_ROW_HEIGHT * len(groups)),
        squeeze=False,
    )
    for axis, (metric, series) in zip(axes[:, 0], groups.items(), strict=True):
        for label, values in series.items():
            axis.plot(steps[: len(values)], values, marker="", label=label)
        axis.set_ylabel(metric)
        axis.grid(alpha=0.3)
        axis.legend(loc="best", fontsize="small")
    axes[-1, 0].set_xlabel("epoch")
    fig.suptitle("Training curves")
    return _write(fig, out)


def _curve_groups(history: list[dict]) -> dict[str, dict[str, list[float]]]:
    """``{metric: {series_label: values}}`` from history records."""
    groups: dict[str, dict[str, list[float]]] = {}
    for record in history or []:
        for key, value in record.items():
            if key == "epoch" or not isinstance(value, (int, float)):
                continue
            metric = key
            for prefix in ("train_", "val_"):
                if key.startswith(prefix):
                    metric = key[len(prefix) :]
                    break
            groups.setdefault(metric, {}).setdefault(key, []).append(float(value))
    return groups


# -------------------------------------------------------- classification


def plot_confusion_matrix(y_true, y_pred, out: str | Path) -> Path:
    """Counts per (true, predicted) class pair, annotated in the cells.

    Args:
        y_true: Ground truth labels.
        y_pred: Predicted labels.
        out: Destination PNG path.

    Returns:
        The written path.
    """
    from sklearn.metrics import confusion_matrix

    labels = _class_labels(y_true, y_pred)
    matrix = confusion_matrix(y_true, y_pred, labels=labels)

    fig, axis = plt.subplots(figsize=_FIGSIZE)
    image = axis.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=axis)
    ticks = range(len(labels))
    axis.set_xticks(ticks, [str(label) for label in labels], rotation=45, ha="right")
    axis.set_yticks(ticks, [str(label) for label in labels])
    axis.set_xlabel("predicted")
    axis.set_ylabel("true")
    axis.set_title("Confusion matrix")
    # Threshold at half the range so annotations stay legible on dark cells.
    threshold = matrix.max() / 2 if matrix.size else 0
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            axis.text(
                j,
                i,
                str(matrix[i, j]),
                ha="center",
                va="center",
                color="white" if matrix[i, j] > threshold else "black",
                fontsize="small",
            )
    return _write(fig, out)


def plot_roc_curves(
    y_true, proba, out: str | Path, classes: list | None = None
) -> tuple[Path, dict[str, float]]:
    """ROC curve(s) plus the AUC scalar(s) the caller logs as metrics.

    Binary problems get one curve; multiclass gets one-vs-rest curves
    overlaid on a single axes with a legend, so the class pulling the macro
    average down is visible against the others.

    Args:
        y_true: Ground truth labels.
        proba: ``(n_samples, n_classes)`` probabilities, in ``classes``
            order.
        out: Destination PNG path.
        classes: Class labels in column order; inferred from ``y_true``
            when omitted.

    Returns:
        ``(path, metrics)`` where metrics carries ``roc_auc`` (the macro
        average for multiclass) and, for multiclass, one
        ``roc_auc_<label>`` per class.
    """
    from sklearn.metrics import auc, roc_curve

    def curve(y_binary, scores):
        fpr, tpr, _ = roc_curve(y_binary, scores)
        return fpr, tpr, float(auc(fpr, tpr))

    fig, axis = plt.subplots(figsize=_FIGSIZE)
    # The no-skill diagonal: a curve is only readable against it.
    axis.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1)
    metrics = _overlay_curves(axis, y_true, proba, classes, curve, "roc_auc")
    axis.set_xlabel("false positive rate")
    axis.set_ylabel("true positive rate")
    axis.set_title("ROC")
    axis.grid(alpha=0.3)
    axis.legend(loc="lower right", fontsize="small")
    return _write(fig, out), metrics


def plot_pr_curves(
    y_true, proba, out: str | Path, classes: list | None = None
) -> tuple[Path, dict[str, float]]:
    """Precision-recall curve(s) plus the average-precision scalar(s).

    Preferred on an imbalanced problem: ROC's false-positive rate is
    diluted by a large negative class, average precision is not.

    Args:
        y_true: Ground truth labels.
        proba: ``(n_samples, n_classes)`` probabilities, in ``classes``
            order.
        out: Destination PNG path.
        classes: Class labels in column order; inferred from ``y_true``
            when omitted.

    Returns:
        ``(path, metrics)`` with ``pr_auc`` (macro average for multiclass)
        and, for multiclass, one ``pr_auc_<label>`` per class.
    """
    from sklearn.metrics import average_precision_score, precision_recall_curve

    def curve(y_binary, scores):
        precision, recall, _ = precision_recall_curve(y_binary, scores)
        return recall, precision, float(average_precision_score(y_binary, scores))

    fig, axis = plt.subplots(figsize=_FIGSIZE)
    metrics = _overlay_curves(axis, y_true, proba, classes, curve, "pr_auc")
    axis.set_xlabel("recall")
    axis.set_ylabel("precision")
    axis.set_title("Precision-recall")
    axis.grid(alpha=0.3)
    axis.legend(loc="lower left", fontsize="small")
    return _write(fig, out), metrics


def _overlay_curves(axis, y_true, proba, classes, curve, metric_name: str) -> dict:
    """Draw one curve per class (or one for binary) and collect the scalars.

    Args:
        curve: ``(y_binary, scores) -> (x, y, area)`` for one class.
        metric_name: Key the area is reported under.
    """
    proba = np.asarray(proba)
    if proba.ndim == 1:
        proba = np.column_stack([1.0 - proba, proba])
    classes = list(classes) if classes is not None else _class_labels(y_true)
    if len(classes) != proba.shape[1]:
        raise ValueError(
            f"{len(classes)} class labels for {proba.shape[1]} probability "
            "columns; the two must describe the same model"
        )
    truth = np.asarray(y_true).astype(str)

    if len(classes) == 2:
        # One curve, for the second class: the "positive" one by convention,
        # and the column inference writes as proba_<positive label>.
        x, y, area = curve((truth == str(classes[1])).astype(int), proba[:, 1])
        axis.plot(x, y, label=f"{classes[1]} (AUC {area:.3f})")
        return {metric_name: area}

    areas = {}
    for index, label in enumerate(classes):
        x, y, area = curve((truth == str(label)).astype(int), proba[:, index])
        axis.plot(x, y, label=f"{label} (AUC {area:.3f})")
        areas[f"{metric_name}_{label}"] = area
    return {metric_name: float(np.mean(list(areas.values()))), **areas}


def plot_calibration_curve(
    y_true, proba, out: str | Path, classes: list | None = None, n_bins: int = 10
) -> Path:
    """Predicted probability against observed frequency, binary only.

    Multiclass calibration is per-class and reads as a different plot, so
    this refuses rather than quietly drawing one class's version of it.

    Args:
        y_true: Ground truth labels.
        proba: Positive-class probabilities, or an ``(n_samples, 2)``
            probability matrix in ``classes`` order.
        out: Destination PNG path.
        classes: Class labels in column order; inferred from ``y_true``
            when omitted.
        n_bins: Number of probability bins the observed frequency is
            averaged within.

    Returns:
        The written path.

    Raises:
        ValueError: If the problem is not binary.
    """
    from sklearn.calibration import calibration_curve

    proba = np.asarray(proba)
    if proba.ndim == 1:
        proba = np.column_stack([1.0 - proba, proba])
    classes = list(classes) if classes is not None else _class_labels(y_true)
    if len(classes) != 2:
        raise ValueError(
            f"Calibration is drawn for binary problems only; got {len(classes)} "
            "classes. Read the per-class ROC/PR curves instead."
        )
    positive = (np.asarray(y_true).astype(str) == str(classes[1])).astype(int)
    observed, predicted = calibration_curve(positive, proba[:, 1], n_bins=n_bins)

    fig, axis = plt.subplots(figsize=_FIGSIZE)
    axis.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1)
    axis.plot(predicted, observed, marker="o", label=f"class {classes[1]}")
    axis.set_xlabel("mean predicted probability")
    axis.set_ylabel("observed frequency")
    axis.set_title("Calibration")
    axis.grid(alpha=0.3)
    axis.legend(loc="best", fontsize="small")
    return _write(fig, out)


# ------------------------------------------------------------- regression


def plot_residuals(y_true, y_pred, out: str | Path) -> Path:
    """Residual distribution beside predicted-vs-actual, on one figure.

    The two panels answer different questions: the histogram shows bias,
    the scatter against the identity line shows where in the target range
    the model departs from it.

    Args:
        y_true: Ground truth values.
        y_pred: Predicted values.
        out: Destination PNG path.

    Returns:
        The written path.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    residual = y_true - y_pred

    fig, (left, right) = plt.subplots(1, 2, figsize=(11.0, 4.5))
    left.hist(residual, bins=30, color="steelblue", edgecolor="white")
    left.axvline(0.0, color="grey", linestyle="--", linewidth=1)
    left.set_xlabel("residual (true - predicted)")
    left.set_ylabel("count")
    left.set_title(f"Residuals (mean {residual.mean():.3f})")
    left.grid(alpha=0.3)

    right.scatter(y_pred, y_true, s=12, alpha=0.5, color="steelblue")
    limits = [
        float(min(y_pred.min(), y_true.min())),
        float(max(y_pred.max(), y_true.max())),
    ]
    right.plot(limits, limits, linestyle="--", color="grey", linewidth=1)
    right.set_xlabel("predicted")
    right.set_ylabel("true")
    right.set_title("Predicted vs actual")
    right.grid(alpha=0.3)
    return _write(fig, out)


# ----------------------------------------------------------- attributions


def plot_feature_importances(
    names: list[str],
    values,
    out: str | Path,
    top_n: int = 20,
    title: str = "Feature importances",
) -> Path:
    """Top-N features as a horizontal bar chart, largest first.

    Ranked by magnitude so signed coefficients sort by influence rather
    than by sign, and drawn horizontally because feature names are long.

    Args:
        names: Feature names, aligned with ``values``.
        values: Importance or coefficient per feature.
        out: Destination PNG path.
        top_n: Maximum number of bars to draw.
        title: Chart title; the drawn and total counts are appended.

    Returns:
        The written path.

    Raises:
        ValueError: If ``names`` and ``values`` disagree in length, which
            would label the bars with the wrong features.
    """
    values = np.asarray(values, dtype=float)
    if len(names) != len(values):
        raise ValueError(
            f"{len(names)} feature names for {len(values)} values; the chart "
            "would label the wrong bars"
        )
    order = np.argsort(np.abs(values))[::-1][: max(top_n, 1)]
    # Reversed: barh draws bottom-up, and the largest belongs at the top.
    order = order[::-1]

    fig, axis = plt.subplots(figsize=(_FIGSIZE[0], max(3.0, 0.3 * len(order) + 1.0)))
    axis.barh([names[i] for i in order], values[order], color="steelblue")
    axis.set_xlabel("importance")
    axis.set_title(f"{title} (top {len(order)} of {len(values)})")
    axis.grid(alpha=0.3, axis="x")
    return _write(fig, out)


def save_current_figure(out: str | Path) -> Path:
    """Write whatever a third-party helper just drew, then close it.

    Supports libraries that plot onto the current figure instead of
    returning one, such as SHAP's ``beeswarm`` and ``bar``. Keeping it here
    means no caller outside this module imports pyplot, so the Agg pin
    above stays the only backend decision in the project.

    Args:
        out: Destination PNG path.

    Returns:
        The written path.
    """
    return _write(plt.gcf(), out)


# ------------------------------------------------------------------ parts


def _write(fig, out: str | Path) -> Path:
    """Save a figure and close it; an unclosed figure leaks across a suite."""
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", path)
    return path


def _class_labels(*arrays) -> list:
    """Sorted union of the labels present, as the class order to plot in."""
    values = np.concatenate([np.asarray(a).reshape(-1) for a in arrays])
    return sorted(np.unique(values).tolist())
