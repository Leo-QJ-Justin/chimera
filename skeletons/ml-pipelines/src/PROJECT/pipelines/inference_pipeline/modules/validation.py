"""Input-side contract checks for serving.

The trainer already realigns columns internally. This module exists so the
pipeline can fail with a message about the input file before a model is
asked to predict on it, and so the checks are testable without
constructing a trainer.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def read_input(path: str | Path) -> pd.DataFrame:
    """Read the inference input; ``.csv``/``.parquet`` chosen by suffix."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Inference input not found: {path}")
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    logger.info("Input %s: %d rows x %d cols", path, len(df), df.shape[1])
    return df


def validate_features(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Enforce the feature contract: exact set, exact order.

    Missing features raise, because a silently absent column becomes an
    all-NaN imputed column and a plausible wrong answer. Extra columns only
    warn, since a model-input table legitimately carries keys and labels.

    Args:
        df: Raw inference input.
        feature_columns: Feature names in the order the model was fitted.

    Returns:
        The frame reindexed to ``feature_columns``.

    Raises:
        ValueError: If any trained-on feature is absent from the input.
    """
    missing = [c for c in feature_columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"Input is missing {len(missing)} feature column(s) the model "
            f"was trained on: {missing}"
        )
    extra = [c for c in df.columns if c not in feature_columns]
    if extra:
        logger.warning(
            "Ignoring %d column(s) not used by the model: %s", len(extra), extra
        )
    # Reindex, never trust the input order: the preprocessor selects by name,
    # but a positional array downstream would not.
    return df[feature_columns]


def validate_keys(df: pd.DataFrame, key_cols: list[str]) -> list[str]:
    """Which key columns survive into the predictions file.

    Missing keys are a warning, not an error, because a serving payload may
    legitimately have none. The evaluation pipeline joins on them, so
    losing them silently would make the predictions unscoreable.

    Args:
        df: Raw inference input.
        key_cols: Key columns the predictions file should carry.

    Returns:
        The subset of ``key_cols`` present in the input.
    """
    present = [c for c in key_cols if c in df.columns]
    missing = sorted(set(key_cols) - set(present))
    if missing:
        logger.warning(
            "Key columns %s absent from input; predictions will be positional "
            "only, and run_evaluation.py cannot join them to ground truth",
            missing,
        )
    return present
