import json

import numpy as np
import pytest

from core import run_artifacts as ra


def test_run_dir_and_latest_pointer_roundtrip(tmp_path):
    ts = ra.generate_timestamp()
    run_dir = ra.make_run_dir(tmp_path, ts)
    assert run_dir.exists()
    ra.save_latest_pointer(tmp_path, ts)
    assert ra.get_latest_timestamp(tmp_path) == ts
    assert ra.resolve_artifact_path(tmp_path) == run_dir


def test_resolve_raises_without_pointer(tmp_path):
    with pytest.raises(FileNotFoundError):
        ra.resolve_artifact_path(tmp_path)


def test_best_pointer_min_mode_monotonic(tmp_path):
    assert ra.save_best_pointer(tmp_path, "t1", 0.5, metric="rmse", mode="min")
    assert not ra.save_best_pointer(tmp_path, "t2", 0.7, metric="rmse", mode="min")
    assert ra.save_best_pointer(tmp_path, "t3", 0.3, metric="rmse", mode="min")
    info = ra.get_best_info(tmp_path)
    assert info["timestamp"] == "t3" and info["value"] == 0.3


def test_best_pointer_max_mode(tmp_path):
    assert ra.save_best_pointer(tmp_path, "t1", 0.6, metric="f1", mode="max")
    assert not ra.save_best_pointer(tmp_path, "t2", 0.5, metric="f1", mode="max")


def test_best_pointer_refuses_metric_mismatch(tmp_path):
    ra.save_best_pointer(tmp_path, "t1", 0.5, metric="rmse", mode="min")
    with pytest.raises(ValueError, match="tracks 'rmse'"):
        ra.save_best_pointer(tmp_path, "t2", 0.9, metric="f1", mode="max")


def test_best_pointer_rejects_bad_mode(tmp_path):
    with pytest.raises(ValueError, match="mode"):
        ra.save_best_pointer(tmp_path, "t1", 0.5, metric="rmse", mode="up")


def test_metadata_envelope_roundtrip(tmp_path):
    ra.save_metadata(
        tmp_path,
        model_type="lightgbm",
        timestamp="20260101_000000",
        feature_columns=["a", "b"],
        target_columns=["y"],
        hyperparameters={"seed": 42},
        training_info={"n": 10},
        files={"model": "model.txt"},
        upstream_config={"clean": True},
    )
    meta = ra.load_metadata(tmp_path)
    assert meta["files"]["model"] == "model.txt"
    assert meta["upstream_config"] == {"clean": True}
    assert "python_version" in meta["environment"]


def test_feature_column_contract():
    meta = {"feature_columns": ["a", "b"]}
    assert ra.validate_feature_columns(meta, None) == ["a", "b"]
    assert ra.validate_feature_columns(meta, ["a", "b"]) == ["a", "b"]
    with pytest.raises(ValueError, match="mismatch"):
        ra.validate_feature_columns(meta, ["b", "a"])


def test_make_serialisable_numpy():
    out = ra.make_serialisable(
        {"arr": np.array([1, 2]), "scalar": np.float64(1.5), "path": None}
    )
    assert out == {"arr": [1, 2], "scalar": 1.5, "path": None}
    json.dumps(out)


def test_config_snapshot(tmp_path):
    path = ra.save_config_snapshot(tmp_path, {"a": {"b": np.int64(1)}})
    import yaml

    assert yaml.safe_load(path.read_text()) == {"a": {"b": 1}}
