"""Run artifact discipline: timestamps, pointers, metadata, snapshots.

One timestamp is generated per run and threaded everywhere. Outputs live
under ``base/<timestamp>/``. Runs are found only through the
latest.json/best.json pointers, never by globbing directories:

- ``latest.json``: the most recent run.
- ``best.json``: monotonic improvement on a declared ``(metric, mode)``.

``metadata.json`` is the reload contract for saved models: the loader
reads metadata first and never guesses at filenames.
"""

import hashlib
import json
import logging
import platform
import subprocess
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Asia/Singapore"
ENVIRONMENT_FILENAME = "environment.json"

# Distribution names, curated rather than a full freeze: the file is meant
# to be read. Anything absent (an optional extra this project never
# installed) is left out rather than recorded as null.
RECORDED_PACKAGES = (
    "numpy",
    "pandas",
    "scikit-learn",
    "pydantic",
    "hydra-core",
    "mlflow",
    "joblib",
    "matplotlib",
    "lightgbm",
    "xgboost",
    "torch",
    "optuna",
    "shap",
)


def generate_timestamp(tz: str = DEFAULT_TZ) -> str:
    """One ``YYYYmmdd_HHMMSS`` timestamp; call once per run and thread it."""
    return datetime.now(ZoneInfo(tz)).strftime("%Y%m%d_%H%M%S")


def make_run_dir(base: str | Path, timestamp: str) -> Path:
    """Create and return ``base/<timestamp>/``.

    Raises:
        FileExistsError: If the dir already exists with content - the
            timestamp is second-granular, so two runs started within the
            same second would otherwise silently clobber each other.
    """
    run_dir = Path(base) / timestamp
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(
            f"Run dir {run_dir} already exists and is non-empty (two runs "
            "started within the same second?) - retry to get a fresh timestamp"
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ---------------------------------------------------------------- pointers


def save_latest_pointer(base: str | Path, timestamp: str) -> None:
    """Point ``latest.json`` at this run.

    Args:
        base: Directory holding the per-run subdirectories.
        timestamp: Run timestamp to record.
    """
    _write_json(Path(base) / "latest.json", {"timestamp": timestamp})


def get_latest_timestamp(base: str | Path) -> str:
    """Read the timestamp of the most recent run.

    Args:
        base: Directory holding the per-run subdirectories.

    Returns:
        The timestamp recorded in ``latest.json``.

    Raises:
        FileNotFoundError: If no run has written a pointer yet.
    """
    pointer = Path(base) / "latest.json"
    if not pointer.exists():
        raise FileNotFoundError(f"No latest.json under {base}")
    return json.loads(pointer.read_text())["timestamp"]


def save_best_pointer(
    base: str | Path,
    timestamp: str,
    value: float,
    metric: str,
    mode: str = "min",
) -> bool:
    """Update ``best.json`` only on monotonic improvement.

    Args:
        base: Directory holding the per-run subdirectories.
        timestamp: Run timestamp to record if this run wins.
        value: The monitored metric's value for this run.
        metric: Metric name, recorded in the pointer so mismatched
            comparisons fail loudly instead of silently.
        mode: ``"min"`` (loss-like) or ``"max"`` (score-like).

    Returns:
        True if this run became the new best.

    Raises:
        ValueError: On an unknown mode, or when the existing pointer
            tracks a different metric.
    """
    if mode not in ("min", "max"):
        raise ValueError(f"mode must be 'min' or 'max', got {mode!r}")
    best_file = Path(base) / "best.json"
    if best_file.exists():
        current = json.loads(best_file.read_text())
        if current.get("metric") != metric:
            raise ValueError(
                f"best.json tracks {current.get('metric')!r}, refusing to "
                f"compare against {metric!r}"
            )
        improved = value < current["value"] if mode == "min" else value > current["value"]
        if not improved:
            return False
    _write_json(
        best_file,
        {"timestamp": timestamp, "metric": metric, "mode": mode, "value": value},
    )
    return True


def get_best_info(base: str | Path) -> dict:
    """Read the best-run pointer.

    Args:
        base: Directory holding the per-run subdirectories.

    Returns:
        The recorded ``timestamp``, ``metric``, ``mode`` and ``value``.

    Raises:
        FileNotFoundError: If no run has qualified as best yet.
    """
    best_file = Path(base) / "best.json"
    if not best_file.exists():
        raise FileNotFoundError(f"No best.json under {base}")
    return json.loads(best_file.read_text())


def resolve_artifact_path(base: str | Path, timestamp: str | None = None) -> Path:
    """The sole read path: explicit timestamp, else follow ``latest.json``."""
    timestamp = timestamp or get_latest_timestamp(base)
    path = Path(base) / timestamp
    if not path.exists():
        raise FileNotFoundError(f"No artifact dir {path}")
    return path


# ---------------------------------------------------------------- metadata


def save_metadata(
    run_dir: str | Path,
    model_type: str,
    timestamp: str,
    feature_columns: list[str],
    target_columns: list[str],
    hyperparameters: dict,
    training_info: dict,
    files: dict[str, str],
    upstream_config: dict | None = None,
    tz: str = DEFAULT_TZ,
) -> Path:
    """Write the ``metadata.json`` reload envelope.

    Args:
        run_dir: Directory the envelope is written into.
        model_type: Trainer family identifier, used to pick a loader.
        timestamp: Run timestamp this directory belongs to.
        feature_columns: Feature names in the exact order the model was
            fitted on; load-time validation compares against this list.
        target_columns: Target names the model predicts.
        hyperparameters: Resolved hyperparameters of the fitted model.
        training_info: Summary of how the fit went, such as row counts,
            fold scores and stopping behaviour.
        files: Artifact kind to filename, so the loader never guesses at
            filenames.
        upstream_config: Data-pipeline config that produced the training
            frame. Embedding it lets inference replay training-time
            preprocessing regardless of what config files say later.
        tz: Timezone for the ``created_at`` stamp.

    Returns:
        Path to the written ``metadata.json``.
    """
    metadata = {
        "model_type": model_type,
        "timestamp": timestamp,
        "created_at": datetime.now(ZoneInfo(tz)).isoformat(),
        "environment": get_environment_info(),
        "feature_columns": feature_columns,
        "target_columns": target_columns,
        "hyperparameters": hyperparameters,
        "training_info": training_info,
        "files": files,
        "upstream_config": upstream_config,
    }
    path = Path(run_dir) / "metadata.json"
    _write_json(path, metadata)
    return path


def load_metadata(run_dir: str | Path) -> dict:
    """Read a run's ``metadata.json``.

    Args:
        run_dir: Directory of the run to reload.

    Returns:
        The envelope written by :func:`save_metadata`.

    Raises:
        FileNotFoundError: If the directory holds no metadata envelope.
    """
    path = Path(run_dir) / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"No metadata.json in {run_dir}")
    return json.loads(path.read_text())


def validate_feature_columns(metadata: dict, expected: list[str] | None) -> list[str]:
    """Enforce the exact feature-order contract on load.

    The first loaded model's columns become canonical; every subsequent
    load must match by exact list equality.

    Args:
        metadata: Envelope from :func:`load_metadata`.
        expected: Canonical column order, or ``None`` on the first load.

    Returns:
        The metadata's feature columns, now canonical.

    Raises:
        ValueError: If the model was saved with a different feature set
            or a different column order.
    """
    columns = metadata["feature_columns"]
    if expected is not None and columns != expected:
        raise ValueError(
            "Feature-column mismatch: model saved with a different feature "
            "set/order than the one already loaded"
        )
    return columns


# ----------------------------------------------------------- provenance


def file_fingerprint(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """Hash a file's bytes to identify the exact content a run consumed.

    Truncated to 16 hex characters like ``core.splits.fingerprint``, so a
    split fingerprint and a data fingerprint read alike side by side in a
    params table. Read in chunks because the model-input table is the one
    file in a run that is allowed to be large.

    Args:
        path: File to hash.
        chunk_size: Bytes read per iteration.

    Returns:
        The first 16 hex characters of the sha256 digest.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def get_git_info() -> dict:
    """Best-effort git provenance; 'N/A' values outside a repo."""

    def _run(args: list[str]) -> str:
        return subprocess.run(
            args, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return {
            "commit": _run(["git", "rev-parse", "--short", "HEAD"]),
            "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
            "dirty": bool(_run(["git", "status", "--porcelain"])),
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": "N/A", "branch": "N/A", "dirty": "N/A"}


def get_environment_info() -> dict:
    """Python/platform plus best-effort library versions."""
    info = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for lib in ("numpy", "pandas", "sklearn", "lightgbm", "torch", "mlflow"):
        try:
            info[lib] = __import__(lib).__version__
        except ImportError:
            pass
    return info


def record_environment(run_dir: str | Path) -> Path:
    """Write ``environment.json``: the interpreter and versions that ran.

    The git commit pins the code and the config snapshot pins the knobs;
    this pins what the code was run against, which is the remaining reason
    a rerun of an otherwise pinned run can disagree - a solver default, a
    serialisation format, a fitted-model pickle.

    Versions are resolved by distribution name through
    ``importlib.metadata``, so the file lists what an install would have to
    provide. The inline block in ``metadata.json`` stays a glance-level
    summary keyed the way the imports are.

    Args:
        run_dir: Directory the file is written into.

    Returns:
        Path to the written ``environment.json``.
    """
    packages = {}
    for name in RECORDED_PACKAGES:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            continue
    path = Path(run_dir) / ENVIRONMENT_FILENAME
    _write_json(path, {"python": sys.version.split()[0], "packages": packages})
    return path


# ------------------------------------------------------------- snapshots


def save_config_snapshot(run_dir: str | Path, config: dict) -> Path:
    """Dump the post-merge, post-override config that actually ran.

    The snapshot records what ran, not what any single file said, so CLI
    overrides and runtime injections must already be applied to ``config``.

    Args:
        run_dir: Directory the snapshot is written into.
        config: Fully resolved configuration mapping.

    Returns:
        Path to the written ``config.yaml``.
    """
    import yaml

    path = Path(run_dir) / "config.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(make_serialisable(config), f, sort_keys=False)
    return path


def make_serialisable(obj):
    """Recursively coerce numpy/path types for JSON/YAML dumping."""
    if isinstance(obj, dict):
        return {str(k): make_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_serialisable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(make_serialisable(payload), indent=2))
