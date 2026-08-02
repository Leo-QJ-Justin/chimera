"""Split records: stable keys, fingerprints, and replaying a run's frames."""

from pathlib import Path

import pandas as pd
import pytest

from PROJECT.core import splits as sp
from PROJECT.core.run_artifacts import load_metadata


@pytest.fixture
def frame():
    return pd.DataFrame(
        {
            "entity": ["a", "a", "b", "b", "c", "c"],
            "ts": [1, 2, 1, 2, 1, 2],
            "x": range(6),
        }
    )


def test_make_key_and_missing_column(frame):
    keys = sp.make_key(frame, ["entity", "ts"])
    assert keys.tolist()[0] == "a|1"
    with pytest.raises(KeyError):
        sp.make_key(frame, ["nope"])


def test_fingerprint_order_insensitive():
    assert sp.fingerprint(["b", "a"]) == sp.fingerprint(["a", "b"])
    assert sp.fingerprint(["a"]) != sp.fingerprint(["a", "b"])


def test_save_load_apply_roundtrip(tmp_path, frame):
    keys = sp.make_key(frame, ["entity", "ts"])
    train, test = keys[:4].tolist(), keys[4:].tolist()
    prints = sp.save_splits(
        tmp_path,
        {"train": train, "test": test},
        key_cols=["entity", "ts"],
        protocol={"mode": "shuffle", "seed": 42},
    )
    assert set(prints) == {"train", "test"}
    payload = sp.load_splits(tmp_path)
    parts = sp.apply_splits(frame, payload)
    assert len(parts["train"]) == 4 and len(parts["test"]) == 2


def test_apply_raises_on_changed_data(tmp_path, frame):
    keys = sp.make_key(frame, ["entity", "ts"]).tolist()
    sp.save_splits(tmp_path, {"train": keys}, key_cols=["entity", "ts"])
    payload = sp.load_splits(tmp_path)
    shrunk = frame.iloc[:3]
    with pytest.raises(ValueError, match="data changed"):
        sp.apply_splits(shrunk, payload)


def test_overlap_check_rejects_leak():
    with pytest.raises(ValueError, match="overlap"):
        sp.overlap_check({"train": ["a", "b"], "test": ["b"]})


def test_folds_may_overlap_holdout_but_not_each_other():
    sp.overlap_check({"train": ["a", "b"], "fold_0": ["a"], "fold_1": ["b"]})
    with pytest.raises(ValueError, match="overlap"):
        sp.overlap_check({"fold_0": ["a"], "fold_1": ["a"]})


class TestLoadSplitFrames:
    """The replay path: a run's own frames, re-derived rather than stored."""

    def test_round_trip_matches_a_manual_rebuild(self, trained_run):
        """What comes back is what the training pipeline built, row for row."""
        run_dir, config = trained_run
        X, y = sp.load_split_frames(run_dir)

        # Rebuilt from the two artifacts by hand, not through apply_splits:
        # the point is that splits.json plus the table is enough.
        features = load_metadata(run_dir)["feature_columns"]
        table = pd.read_parquet(config.processed_path)
        payload = sp.load_splits(run_dir)
        keys = sp.make_key(table, payload["key_cols"])

        assert set(X) == set(y) == set(payload["splits"])
        for name, members in payload["splits"].items():
            rows = table[keys.isin(set(members))]
            pd.testing.assert_frame_equal(X[name], rows[features])
            pd.testing.assert_series_equal(y[name], rows[config.target])

    def test_a_rewritten_table_is_refused(self, trained_run):
        """One changed feature value, every key intact - the hash is the catch.

        Membership still resolves, so ``apply_splits`` alone would hand back
        frames that look right and are not the ones the run trained on.
        """
        run_dir, config = trained_run
        table = pd.read_parquet(config.processed_path)
        table.loc[0, "num_a"] = table.loc[0, "num_a"] + 1.0
        table.to_parquet(config.processed_path, index=False)

        with pytest.raises(ValueError, match="no longer exists at that path"):
            sp.load_split_frames(run_dir)

    def test_a_missing_table_names_the_path_the_run_recorded(self, trained_run):
        run_dir, config = trained_run
        Path(config.processed_path).unlink()
        with pytest.raises(FileNotFoundError, match="model_input.parquet"):
            sp.load_split_frames(run_dir)
