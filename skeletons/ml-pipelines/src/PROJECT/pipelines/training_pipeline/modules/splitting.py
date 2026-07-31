"""Split protocols and feature resolution - the training pipeline's own job.

The data pipeline never splits (D5); everything here is why. Two things
live in this module:

- **The holdout split** the run trains on, recorded by stable key
  membership plus a fingerprint (D8), never by positional index.
- **The CV splitter factory**, chosen from the configured split mode
  rather than hardcoded. A ``TimeSeriesSplit`` baked into a base class is
  wrong for i.i.d. tabular data and a shuffled ``KFold`` is wrong for time
  series; D9 says the choice is per problem type, so it comes from config.

Stateless functions, hence ``modules/``.
"""

import logging

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
from sklearn.model_selection import (
    GroupKFold,
    KFold,
    StratifiedKFold,
    TimeSeriesSplit,
    train_test_split,
)

from ....core.splits import make_key, save_splits

logger = logging.getLogger(__name__)


def resolve_feature_columns(df: pd.DataFrame, config) -> tuple[list[str], list[str]]:
    """Return ``(numeric, categorical)`` feature columns.

    Declared lists win. Empty lists fall back to dtype inference with a
    warning: convenient on day one, but the declared form is what pins the
    feature contract, so the warning is deliberate nagging.

    Datetime columns are never inferred as features - they are split keys
    and a leak risk; derive calendar parts in the data pipeline instead.
    """
    if config.numeric_features or config.categorical_features:
        return list(config.numeric_features), list(config.categorical_features)

    excluded = set(config.key_cols) | {config.target}
    numeric, categorical, skipped = [], [], []
    for col in df.columns:
        if col in excluded:
            continue
        if is_datetime64_any_dtype(df[col]):
            skipped.append(col)
        elif is_numeric_dtype(df[col]):
            numeric.append(col)
        else:
            categorical.append(col)
    logger.warning(
        "No feature lists configured; inferred %d numeric + %d categorical "
        "by dtype (skipped datetime %s). Declare them in training.yaml once "
        "the feature set settles.",
        len(numeric),
        len(categorical),
        skipped,
    )
    return numeric, categorical


def split_frame(df: pd.DataFrame, split, target: str) -> dict[str, pd.DataFrame]:
    """Split per the configured protocol into train/val/test frames."""
    if split.mode == "temporal":
        return temporal_split(df, split)
    if split.mode == "group":
        raise NotImplementedError(
            "split.mode='group' is not implemented in the skeleton; add a "
            "GroupShuffleSplit branch here and record group ids in "
            "split.key_cols"
        )

    stratify = df[target] if split.mode == "stratified" else None
    train, rest = train_test_split(
        df,
        train_size=split.train_size,
        random_state=split.seed,
        shuffle=True,
        stratify=stratify,
    )
    # val_size and test_size are fractions of the whole, so rescale against
    # the remainder.
    val_fraction = split.val_size / (split.val_size + split.test_size)
    stratify_rest = rest[target] if split.mode == "stratified" else None
    val, test = train_test_split(
        rest,
        train_size=val_fraction,
        random_state=split.seed,
        shuffle=True,
        stratify=stratify_rest,
    )
    return {"train": train, "val": val, "test": test}


def temporal_split(df: pd.DataFrame, split) -> dict[str, pd.DataFrame]:
    """Boundary dates from config; membership still recorded (D8)."""
    stamps = pd.to_datetime(df[split.time_col], errors="coerce")
    val_start = pd.Timestamp(split.boundaries["val_start"])
    test_start = pd.Timestamp(split.boundaries["test_start"])
    if val_start >= test_start:
        raise ValueError("boundaries.val_start must precede boundaries.test_start")
    frames = {
        "train": df[stamps < val_start],
        "val": df[(stamps >= val_start) & (stamps < test_start)],
        "test": df[stamps >= test_start],
    }
    empty = [name for name, frame in frames.items() if frame.empty]
    if empty:
        raise ValueError(
            f"Temporal boundaries leave {empty} empty; check split.boundaries "
            f"against the range of {split.time_col}"
        )
    return frames


def record_splits(run_dir, frames: dict[str, pd.DataFrame], split) -> dict[str, str]:
    """Persist realized membership by stable key; return fingerprints."""
    members = {
        name: make_key(frame, list(split.key_cols)).tolist()
        for name, frame in frames.items()
    }
    return save_splits(run_dir, members, list(split.key_cols), split.model_dump())


def make_cv_splitter(mode: str, n_splits: int, seed: int):
    """The cross-validation splitter the configured protocol implies (D9).

    Args:
        mode: The run's ``split.mode``.
        n_splits: Number of folds.
        seed: Threaded into the shuffled splitters so folds reproduce.

    Returns:
        ``StratifiedKFold`` for stratified, ``KFold`` for shuffle,
        ``TimeSeriesSplit`` for temporal (expanding window, never
        shuffled), ``GroupKFold`` for group.
    """
    if mode == "temporal":
        # No shuffle and no seed by construction: a temporal fold is defined
        # by order, and shuffling it is the leak D9 exists to prevent.
        return TimeSeriesSplit(n_splits=n_splits)
    if mode == "group":
        return GroupKFold(n_splits=n_splits)
    if mode == "stratified":
        return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return KFold(n_splits=n_splits, shuffle=True, random_state=seed)
