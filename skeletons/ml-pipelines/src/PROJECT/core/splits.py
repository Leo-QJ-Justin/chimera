"""Split reproducibility: persist membership, not just the recipe.

Seed + protocol is the *generator* of a split; the artifact written here
is the *record*. Membership is stored as stable row keys (entity id,
timestamp, or a durable sample id), never positional indices - positional
indices break silently when the gold table is regenerated.

The fingerprint (sha256 of the sorted membership) is logged as a run
param so split-identity across runs is checkable at a glance.
"""

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

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
    """Reproduce a recorded split exactly on a (regenerated) gold table.

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
