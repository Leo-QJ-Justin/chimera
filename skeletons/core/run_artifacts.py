"""Run artifact discipline: timestamps, pointers, metadata, snapshots.

One timestamp is generated per run and threaded everywhere. Outputs live
under ``base/<timestamp>/``. Two pointer files at the base dir are the
only read path - nothing globs directories:

- ``latest.json``: the most recent run.
- ``best.json``: monotonic improvement on a declared ``(metric, mode)``.

``metadata.json`` is the reload contract for saved models: the loader
reads metadata first and never guesses at filenames.
"""

import json
import logging
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Asia/Singapore"


def generate_timestamp(tz: str = DEFAULT_TZ) -> str:
    """One ``YYYYmmdd_HHMMSS`` timestamp; call once per run and thread it."""
    return datetime.now(ZoneInfo(tz)).strftime("%Y%m%d_%H%M%S")


def make_run_dir(base: str | Path, timestamp: str) -> Path:
    """Create and return ``base/<timestamp>/``."""
    run_dir = Path(base) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ---------------------------------------------------------------- pointers


def save_latest_pointer(base: str | Path, timestamp: str) -> None:
    _write_json(Path(base) / "latest.json", {"timestamp": timestamp})


def get_latest_timestamp(base: str | Path) -> str:
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

    ``files`` maps artifact kind to filename so the loader never guesses.
    ``upstream_config`` embeds the data-pipeline config that produced the
    training frame, so inference replays training-time preprocessing
    regardless of what config files say later.
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
    path = Path(run_dir) / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"No metadata.json in {run_dir}")
    return json.loads(path.read_text())


def validate_feature_columns(metadata: dict, expected: list[str] | None) -> list[str]:
    """Enforce the exact feature-order contract on load.

    The first loaded model's columns become canonical; every subsequent
    load must match by exact list equality.
    """
    columns = metadata["feature_columns"]
    if expected is not None and columns != expected:
        raise ValueError(
            "Feature-column mismatch: model saved with a different feature "
            "set/order than the one already loaded"
        )
    return columns


# ----------------------------------------------------------- provenance


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


# ------------------------------------------------------------- snapshots


def save_config_snapshot(run_dir: str | Path, config: dict) -> Path:
    """Dump the post-merge, post-override config that actually ran.

    The snapshot records what ran, not what any single file said - CLI
    overrides and runtime injections must already be applied to ``config``.
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
