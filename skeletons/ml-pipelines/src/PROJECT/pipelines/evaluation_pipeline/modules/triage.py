"""Error triage: which rows went wrong, and how badly.

An aggregate metric states the outcome; triage shows the rows behind it.
Producing the ranking here keeps it reproducible instead of rebuilt by
hand for each investigation.

Two rankings, one per task:

- Classification: misclassified rows ordered by the model's confidence in
  the wrong answer. A confident mistake points at a labelling problem, a
  feature bug, or a genuinely hard region; an unconfident one usually sits
  on the decision boundary.
- Regression: rows ordered by ``|error|``, with the signed residual kept
  so systematic bias is visible rather than averaged away.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def worst_cases(
    joined: pd.DataFrame,
    target: str,
    prediction_col: str,
    task: str,
    top_n: int,
    key_cols: list[str],
    drill_down_columns: list[str] | None = None,
) -> pd.DataFrame:
    """The top-N worst rows, with enough context to read them.

    Args:
        joined: Predictions joined to ground truth.
        target: Ground-truth column.
        prediction_col: Prediction column.
        task: ``"classification"`` or ``"regression"``.
        top_n: Rows to return. 0 returns an empty frame.
        key_cols: Row identity, always carried.
        drill_down_columns: Extra columns to carry so a bad row can be
            read without a second join.

    Returns:
        A frame ordered worst-first, carrying keys, truth, prediction, the
        error/confidence column, and the requested drill-down columns.
    """
    if top_n <= 0:
        return joined.iloc[:0].copy()
    columns = [*key_cols, target, prediction_col, *(drill_down_columns or [])]
    columns = [c for c in dict.fromkeys(columns) if c in joined.columns]

    if task == "regression":
        frame = joined.assign(
            residual=joined[target] - joined[prediction_col],
        )
        frame["abs_error"] = frame["residual"].abs()
        ranked = frame.sort_values("abs_error", ascending=False)
        ranked = ranked[[*columns, "residual", "abs_error"]]
        return ranked.head(top_n).reset_index(drop=True)

    frame = joined.copy()
    frame["correct"] = frame[target] == frame[prediction_col]
    frame["confidence"] = predicted_confidence(frame, prediction_col)
    wrong = frame[~frame["correct"]]
    if wrong.empty:
        logger.info("No misclassifications to triage")
        return wrong[[*columns, "confidence"]].reset_index(drop=True)
    # Descending confidence: the model was surest about these and still wrong.
    ranked = wrong.sort_values("confidence", ascending=False, na_position="last")
    return ranked[[*columns, "confidence"]].head(top_n).reset_index(drop=True)


def predicted_confidence(frame: pd.DataFrame, prediction_col: str) -> pd.Series:
    """Probability the model assigned to the class it predicted.

    Reads the ``proba_<label>`` columns the inference pipeline writes.

    Args:
        frame: Joined predictions, possibly carrying ``proba_*`` columns.
        prediction_col: Column holding the predicted label.

    Returns:
        The predicted class's probability per row, or all-NaN when the
        trainer exposed no probabilities. The ranking then falls back to
        an arbitrary but stable order rather than an invented confidence.
    """
    proba_cols = [c for c in frame.columns if c.startswith("proba_")]
    if not proba_cols:
        return pd.Series(np.nan, index=frame.index)
    labels = {c: c[len("proba_") :] for c in proba_cols}
    predicted = frame[prediction_col].astype(str)
    confidence = pd.Series(np.nan, index=frame.index)
    for column, label in labels.items():
        mask = predicted == label
        confidence[mask] = frame.loc[mask, column]
    return confidence


def error_summary(
    joined: pd.DataFrame, target: str, prediction_col: str, task: str
) -> dict:
    """Summarise the error shape: counts, or residual moments.

    Args:
        joined: Predictions joined to ground truth.
        target: Ground-truth column.
        prediction_col: Prediction column.
        task: ``"classification"`` or ``"regression"``.

    Returns:
        Row count plus correct/wrong counts for classification, or
        residual mean, standard deviation and maximum absolute error for
        regression.
    """
    if task == "regression":
        residual = joined[target] - joined[prediction_col]
        return {
            "n_rows": int(len(joined)),
            "residual_mean": float(residual.mean()),
            "residual_std": float(residual.std()),
            "abs_error_max": float(residual.abs().max()),
        }
    correct = int((joined[target] == joined[prediction_col]).sum())
    return {
        "n_rows": int(len(joined)),
        "n_correct": correct,
        "n_wrong": int(len(joined) - correct),
    }


def to_markdown(frame: pd.DataFrame, empty_note: str = "_none_") -> str:
    """Render a frame as a markdown table, without requiring tabulate.

    Args:
        frame: Frame to render.
        empty_note: Text returned in place of a table when the frame is
            empty.

    Returns:
        The markdown table, or ``empty_note``.
    """
    if frame.empty:
        return empty_note
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    divider = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = [
        "| " + " | ".join(_cell(v) for v in record) + " |"
        for record in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, divider, *rows])


def _cell(value) -> str:
    """Format one table cell, fixing floats to four decimals."""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
