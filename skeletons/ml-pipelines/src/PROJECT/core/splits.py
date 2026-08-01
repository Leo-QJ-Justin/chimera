"""Split reproducibility: persist membership, not just the recipe.

Seed + protocol is the *generator* of a split; the artifact written here
is the *record*. Membership is stored as stable row keys (entity id,
timestamp, or a durable sample id), never positional indices - positional
indices break silently when the model-input table is regenerated.

The fingerprint (sha256 of the sorted membership) is logged as a run
param so split-identity across runs is checkable at a glance.

``load_split_frames`` is the read side of that record: membership plus the
run's content hash of the model-input table is enough to hand back exactly
the frames a past run trained on, without any run ever storing a copy of
them.
"""

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from .run_artifacts import file_fingerprint, load_metadata

logger = logging.getLogger(__name__)

SPLITS_FILENAME = "splits.json"


def make_key(df: pd.DataFrame, key_cols: list[str]) -> pd.Series:
    """A stable string key per row from the declared key columns."""
    missing = [c for c in key_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Key columns missing from frame: {missing}")
    return df[key_cols].astype(str).agg("|".join, axis=1)


def fingerprint(members: list[str]) -> str:
    """sha256 over the sorted membership; order-insensitive identity."""
    digest = hashlib.sha256("\n".join(sorted(members)).encode())
    return digest.hexdigest()[:16]


def save_splits(
    run_dir: str | Path,
    splits: dict[str, list[str]],
    key_cols: list[str],
    protocol: dict | None = None,
) -> dict:
    """Persist realized split membership as a run artifact.

    Args:
        splits: Split name -> member keys. Holdout: ``{"train": [...],
            "test": [...]}``. CV: one entry per fold assignment
            (``{"fold_0": [...], ...}``). Temporal: include the boundary
            dates in ``protocol`` *plus* the realized membership here.
        key_cols: The columns the keys were built from, recorded so a
            reader can rebuild them.
        protocol: The recipe (mode, sizes, seed, boundary dates) for
            human context; the membership is the ground truth.

    Returns:
        ``{split_name: fingerprint}`` - log these as run params.
    """
    overlap_check(splits)
    prints = {name: fingerprint(members) for name, members in splits.items()}
    payload = {
        "key_cols": key_cols,
        "protocol": protocol or {},
        "fingerprints": prints,
        "splits": splits,
    }
    path = Path(run_dir) / SPLITS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    logger.info(
        "Saved splits %s to %s",
        {k: len(v) for k, v in splits.items()},
        path,
    )
    return prints


def load_splits(run_dir: str | Path) -> dict:
    path = Path(run_dir) / SPLITS_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"No {SPLITS_FILENAME} in {run_dir}")
    return json.loads(path.read_text())


def apply_splits(df: pd.DataFrame, splits_payload: dict) -> dict[str, pd.DataFrame]:
    """Reproduce a recorded split exactly on a (regenerated) model-input table.

    Raises:
        ValueError: If any recorded member is absent from the frame - the
            data changed since the split was recorded, which must surface,
            not silently shrink a split.
    """
    keys = make_key(df, splits_payload["key_cols"])
    out = {}
    for name, members in splits_payload["splits"].items():
        member_set = set(members)
        mask = keys.isin(member_set)
        found = int(mask.sum())
        if found != len(member_set):
            raise ValueError(
                f"Split {name!r}: {len(member_set) - found} recorded members "
                "not present in the frame - data changed since recording"
            )
        out[name] = df[mask]
    return out


def load_split_frames(
    run_dir: str | Path, processed_path: str | Path | None = None
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.Series]]:
    """Hand back exactly the frames a recorded run trained on.

    The documented answer to "give me what run X trained on". Nothing is
    stored to make it work: the run recorded split membership by stable key
    and the content hash of the table those keys point into, so the frames
    are *re-derived* - same rows, same feature order, same target - and both
    halves of that record are verified before anything comes back.

    Every set derived downstream of the split replays from these frames via
    the seeds in the run's ``config.yaml``: the train+val pool a pooled
    family fits on, the holdout a standing-val search carves, the CV folds.
    Those are recipes, and recipes reproduce; this function supplies the
    roots they run on.

    Args:
        run_dir: A training run directory (``metadata.json`` + ``splits.json``).
        processed_path: The model-input table, when it has moved since the
            run; defaults to the path the run recorded.

    Returns:
        ``(X, y)``, each keyed by split name, exactly as the training
        pipeline built them.

    Raises:
        FileNotFoundError: The table is not where the run said it was.
        ValueError: Its bytes changed since the run read them, or a
            recorded member is no longer in it.
    """
    metadata = load_metadata(run_dir)
    info = metadata["training_info"]
    recorded_path = info["processed_path"]
    path = Path(processed_path or recorded_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model-input table {path} not found; the run recorded "
            f"{recorded_path!r} - pass processed_path= if it moved"
        )
    # Runs written before the fingerprint existed are read on membership
    # alone; apply_splits still catches a table that lost rows.
    recorded_fp = info.get("processed_fingerprint")
    if recorded_fp and file_fingerprint(path) != recorded_fp:
        raise ValueError(
            f"Content hash of {path} is not the one this run read: the data "
            "this run trained on no longer exists at that path (regenerate it "
            "from the run's config.yaml, or point processed_path= at a copy)"
        )
    frames = apply_splits(pd.read_parquet(path), load_splits(run_dir))
    features = metadata["feature_columns"]
    target = metadata["target_columns"][0]
    return (
        {name: frame[features] for name, frame in frames.items()},
        {name: frame[target] for name, frame in frames.items()},
    )


def overlap_check(splits: dict[str, list[str]]) -> None:
    """Raise if any key appears in more than one non-fold split.

    Fold entries (names starting with ``fold_``) are exempt from
    cross-fold checks against each other only when compared to the
    training pool they are drawn from; folds must still not overlap
    among themselves.
    """
    names = list(splits)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if a.startswith("fold_") != b.startswith("fold_"):
                continue  # fold vs holdout overlap is legitimate
            common = set(splits[a]) & set(splits[b])
            if common:
                raise ValueError(
                    f"Splits {a!r} and {b!r} overlap on {len(common)} keys "
                    f"(e.g. {sorted(common)[:3]})"
                )
