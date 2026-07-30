import pandas as pd
import pytest

from core import splits as sp


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
