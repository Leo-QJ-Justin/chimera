"""Stateless cleaning and feature functions.

The contract: everything in this module is stateless. It may look at a
row, a config value, or a column's declared dtype, but it may never learn
a statistic from the training data that inference would have to reuse.
Anything that needs ``.fit()`` - an imputer's median, a scaler's mean, an
encoder's category list - lives inside a trainer, not the data pipeline,
so fitted state refits per fold and serializes with the model.

Being stateless is also why these are plain functions in ``modules/``
rather than objects in ``classes/``: there is nothing to hold.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ....core.run_artifacts import read_table
from ....schemas import CleaningConfig, FeatureEngineeringConfig

logger = logging.getLogger(__name__)


def load_raw(path: str | Path, date_col: str | None = None) -> pd.DataFrame:
    """Read the raw table and parse its date column.

    Args:
        path: Raw file, ``.csv`` or ``.parquet``.
        date_col: Column to coerce to datetime when present; unparseable
            values become NaT rather than aborting the read, so the
            cleaning stage reports them as a rejection count.

    Returns:
        The raw frame.
    """
    df = read_table(path)
    if date_col and date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    logger.info("Loaded %s: %d rows x %d cols", path, len(df), df.shape[1])
    return df


def clean(
    df: pd.DataFrame, cleaning: CleaningConfig, key_cols: list[str]
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Row-level cleaning. Stateless - see the module docstring.

    Row drops live here rather than in a fitted transformer because a
    transformer inside the model pipeline cannot drop rows or touch ``y``.

    Args:
        df: The raw frame.
        cleaning: Config knobs (sentinels, dedup, required columns).
        key_cols: Dedup subset when ``cleaning.dedup_subset`` is null.

    Returns:
        ``(clean_frame, rejection_counts)``. The counts are per-reason, so
        a run reports why rows disappeared and not only how many.
    """
    counts: dict[str, int] = {"input_rows": len(df)}
    df = df.copy()

    if cleaning.strip_whitespace:
        for col in df.select_dtypes(include="object"):
            df[col] = df[col].str.strip()

    if cleaning.sentinel_values:
        before = int(df.isna().sum().sum())
        df = df.replace(cleaning.sentinel_values, np.nan)
        counts["sentinels_to_nan"] = int(df.isna().sum().sum()) - before

    if cleaning.drop_duplicates:
        subset = cleaning.dedup_subset or key_cols
        missing = [c for c in subset if c not in df.columns]
        if missing:
            raise KeyError(f"Dedup subset columns absent from frame: {missing}")
        before = len(df)
        df = df.drop_duplicates(subset=subset, keep="first")
        counts["dropped_duplicate_keys"] = before - len(df)

    for col in cleaning.drop_rows_missing:
        if col not in df.columns:
            raise KeyError(f"drop_rows_missing names an absent column: {col!r}")
        before = len(df)
        df = df[df[col].notna()]
        counts[f"dropped_missing_{col}"] = before - len(df)

    counts["output_rows"] = len(df)
    for reason, n in counts.items():
        logger.info("Cleaning %s: %d", reason, n)
    return df.reset_index(drop=True), counts


def engineer_features(
    df: pd.DataFrame, features: FeatureEngineeringConfig, date_col: str | None
) -> pd.DataFrame:
    """Derive stateless features. Stateless - see the module docstring.

    Calendar parts are the reference case: they depend only on the row.
    Replace the body with the project's own derivations; anything that
    needs a fitted statistic goes in the training pipeline instead.

    Args:
        df: Cleaned frame.
        features: Feature-engineering knobs.
        date_col: Timestamp column the calendar parts derive from.

    Returns:
        A copy of the frame with derived columns added and configured
        columns dropped.
    """
    df = df.copy()
    if features.date_parts and date_col and date_col in df.columns:
        stamps = pd.to_datetime(df[date_col], errors="coerce")
        df[f"{date_col}_month"] = stamps.dt.month
        df[f"{date_col}_dayofweek"] = stamps.dt.dayofweek
        logger.info("Added calendar parts from %s", date_col)

    drop = [c for c in features.drop_columns if c in df.columns]
    if drop:
        df = df.drop(columns=drop)
        logger.info("Dropped configured columns: %s", drop)
    return df
