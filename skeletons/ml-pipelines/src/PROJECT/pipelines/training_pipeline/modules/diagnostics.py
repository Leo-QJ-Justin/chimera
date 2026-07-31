"""Post-fit diagnostics: what the fitted model itself can be asked to show.

Model-based by definition, which is why they live in the training pipeline
rather than beside the evaluation report: a training curve exists only
while the history is in memory, and SHAP needs the estimator's internals,
not its predictions. The prediction-based figures (confusion matrix, ROC,
calibration, residuals) belong to the evaluation pipeline, which is where
the predictions are.

This module *reads* trainer state and never writes it, and it is called by
the orchestrator rather than by a trainer - that is what keeps trainers
free of tracking and plotting code (a trainer captures ``history``, it does
not draw it).

Everything is written into ``<run_dir>/plots/``. Nothing here uploads
anything: the pipeline logs the whole run directory as MLflow artifacts at
the end of the run, so a file written here is an artifact for free.

Every step is individually guarded. A diagnostic that fails costs the run
one warning line and nothing else - the same contract model logging has.
"""

import logging
from pathlib import Path

import numpy as np

from ....core.plots import (
    plot_feature_importances,
    plot_training_curves,
    save_current_figure,
)
from .preprocessing import transformed_feature_names

logger = logging.getLogger(__name__)

PLOTS_DIRNAME = "plots"
CURVES_FILENAME = "training_curves.png"
IMPORTANCES_FILENAME = "feature_importances.png"
IMPORTANCES_CSV = "feature_importances.csv"
SHAP_BEESWARM_FILENAME = "shap_beeswarm.png"
SHAP_BAR_FILENAME = "shap_bar.png"

# Families whose estimator has no per-feature attribution to read. Torch gets
# curves only: gradient attributions for an MLP are a different tool
# (captum), not a variant of feature_importances_.
_NO_ATTRIBUTION = ("torch",)


def _import_shap():
    """Guarded import: shap is the optional ``explain`` extra.

    Returns None rather than raising - a missing optional explainer is a
    skipped step, not a failed run.
    """
    try:
        import shap
    except ImportError:
        logger.info(
            "diagnostics.shap.enabled=true but shap is not installed; skipping "
            "the SHAP step (`uv add shap`, or install the 'explain' extra)"
        )
        return None
    return shap


def run_diagnostics(run_dir, trainer, options, X_val=None) -> list[Path]:
    """Draw every diagnostic this trainer can support.

    Called by the orchestrator once the fit is done and only when
    ``diagnostics.enabled`` is on - the switch is checked at the call site
    so a disabled run does not even open a stage timer.

    Args:
        run_dir: The run directory; figures land in its ``plots/``.
        trainer: The **fitted** trainer.
        options: The run's :class:`~PROJECT.schemas.DiagnosticsConfig`.
        X_val: The validation features, used as the SHAP background sample.
            None skips the SHAP step.

    Returns:
        The files written, in the order they were drawn.
    """
    plots_dir = Path(run_dir) / PLOTS_DIRNAME
    written: list[Path] = []
    written += _attempt("training curves", _training_curves, trainer, plots_dir)
    written += _attempt("feature importances", _importances, trainer, plots_dir)
    if options.shap.enabled:
        written += _attempt(
            "SHAP attributions", _shap_plots, trainer, X_val, plots_dir, options.shap
        )
    else:
        logger.info("diagnostics.shap.enabled=false; no SHAP attributions")
    logger.info("Wrote %d diagnostic artifact(s) under %s", len(written), plots_dir)
    return written


def _attempt(what: str, step, *args) -> list[Path]:
    """Run one diagnostic step; a failure is a warning, never an abort."""
    try:
        return step(*args)
    except Exception as e:
        logger.warning(
            "Diagnostic %r failed (%s); the run itself is intact", what, e
        )
        return []


# ------------------------------------------------------------------ steps


def _training_curves(trainer, plots_dir: Path) -> list[Path]:
    """Per-iteration curves, for whichever families recorded a history."""
    history = getattr(trainer, "history", None)
    if not history:
        logger.info(
            "%s records no per-iteration history; no training curves",
            trainer.model_type,
        )
        return []
    path = plot_training_curves(history, plots_dir / CURVES_FILENAME)
    return [path] if path else []


def _importances(trainer, plots_dir: Path) -> list[Path]:
    """Importances or coefficients, plus the full ranking as a CSV.

    The CSV is the point as much as the chart: the figure shows the top
    slice, the CSV is what a follow-up analysis joins against.
    """
    if trainer.model_type in _NO_ATTRIBUTION:
        logger.info(
            "%s exposes no per-feature attribution; curves only", trainer.model_type
        )
        return []
    estimator = getattr(trainer, "estimator", None)
    values, title = _attribution(estimator)
    if values is None:
        logger.info(
            "%s exposes neither feature_importances_ nor coef_; no importance chart",
            trainer.model_type,
        )
        return []
    names = transformed_feature_names(
        trainer.preprocessor, trainer.feature_columns, n_features=len(values)
    )
    path = plot_feature_importances(
        names, values, plots_dir / IMPORTANCES_FILENAME, title=title
    )
    csv_path = plots_dir / IMPORTANCES_CSV
    _write_importances_csv(csv_path, names, values)
    return [path, csv_path]


def _attribution(estimator) -> tuple[np.ndarray | None, str]:
    """The estimator's per-feature vector, and what to call it.

    Multiclass coefficients are one row per class; they are reduced to
    mean absolute weight, because a chart of a (classes x features) matrix
    is not a chart anyone reads.
    """
    importances = getattr(estimator, "feature_importances_", None)
    if importances is not None:
        return np.asarray(importances, dtype=float), "Feature importances"
    coefficients = getattr(estimator, "coef_", None)
    if coefficients is None:
        return None, ""
    coefficients = np.asarray(coefficients, dtype=float)
    if coefficients.ndim == 1 or coefficients.shape[0] == 1:
        return coefficients.reshape(-1), "Coefficients"
    return np.abs(coefficients).mean(axis=0), "Mean |coefficient| across classes"


def _write_importances_csv(path: Path, names: list[str], values: np.ndarray) -> None:
    """The full ranking, largest magnitude first."""
    import pandas as pd

    frame = pd.DataFrame({"feature": names, "importance": values})
    frame = frame.reindex(frame["importance"].abs().sort_values(ascending=False).index)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    logger.info("Wrote %s", path)


def _shap_plots(trainer, X_val, plots_dir: Path, shap_options) -> list[Path]:
    """Beeswarm + bar SHAP summaries over a sample of validation rows.

    ``shap.Explainer`` dispatches on the estimator (TreeExplainer for the
    tree families, LinearExplainer for logistic regression), so this needs
    no per-family table of its own.
    """
    if trainer.model_type in _NO_ATTRIBUTION:
        logger.info(
            "SHAP is skipped for %s; gradient attributions for a neural net are "
            "a different tool (captum), not a variant of this one",
            trainer.model_type,
        )
        return []
    if X_val is None or len(X_val) == 0:
        logger.info("No validation rows to explain; skipping SHAP")
        return []
    shap = _import_shap()
    if shap is None:
        return []

    sample = _sample(X_val, shap_options.sample_size, trainer.seed)
    matrix = trainer.transformed(sample)
    explanation = _reduce_to_one_output(shap.Explainer(trainer.estimator, matrix)(matrix))

    shap.plots.beeswarm(explanation, max_display=shap_options.max_display, show=False)
    beeswarm = save_current_figure(plots_dir / SHAP_BEESWARM_FILENAME)
    shap.plots.bar(explanation, max_display=shap_options.max_display, show=False)
    bar = save_current_figure(plots_dir / SHAP_BAR_FILENAME)
    return [beeswarm, bar]


def _sample(X_val, sample_size: int, seed: int):
    """A deterministic sample of the validation frame, or all of it."""
    if len(X_val) <= sample_size:
        return X_val
    return X_val.sample(sample_size, random_state=seed)


def _reduce_to_one_output(explanation):
    """Collapse a per-class explanation to the one the summaries can draw.

    Tree explainers return ``(rows, features, classes)`` for classifiers.
    The last class is taken - the positive one for a binary problem, which
    is the same convention the ROC curve uses.
    """
    if getattr(explanation, "values", np.empty(0)).ndim < 3:
        return explanation
    logger.info("SHAP returned per-class values; summarising the last class")
    return explanation[..., -1]
