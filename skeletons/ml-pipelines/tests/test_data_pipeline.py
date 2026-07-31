"""Data pipeline: the stateless contract and the output guarantees."""

import numpy as np
import pandas as pd
import pytest

# pytest puts tests/ on sys.path (importmode=prepend), so conftest's
# schema-derived constants are importable by name.
from conftest import TEST_DATE_COL, TEST_KEY_COLS, TEST_TARGET
from PROJECT.pipelines.data_pipeline import (
    DataPipeline,
    clean,
    engineer_features,
    load_manifest,
)
from PROJECT.schemas import CleaningConfig, DataPipelineConfig, FeatureEngineeringConfig


def _cleaning(**overrides) -> CleaningConfig:
    base = {"sentinel_values": [-999, "NA"], "drop_rows_missing": [TEST_TARGET]}
    return CleaningConfig(**{**base, **overrides})


class TestClean:
    def test_drops_duplicate_keys_and_counts_them(self, synthetic_frame):
        doubled = pd.concat([synthetic_frame, synthetic_frame.head(5)])
        cleaned, counts = clean(doubled, _cleaning(), TEST_KEY_COLS)
        assert counts["dropped_duplicate_keys"] == 5
        assert not cleaned.duplicated(subset=TEST_KEY_COLS).any()

    def test_sentinels_become_nan(self, synthetic_frame):
        frame = synthetic_frame.copy()
        frame.loc[0:2, "num_a"] = -999
        frame.loc[3, "cat_a"] = "NA"
        cleaned, counts = clean(frame, _cleaning(), TEST_KEY_COLS)
        assert counts["sentinels_to_nan"] == 4
        assert cleaned.loc[0:2, "num_a"].isna().all()
        assert pd.isna(cleaned.loc[3, "cat_a"])

    def test_rows_missing_the_target_are_dropped_with_a_reason(self, synthetic_frame):
        frame = synthetic_frame.astype({TEST_TARGET: float})
        frame.loc[0:1, TEST_TARGET] = np.nan
        cleaned, counts = clean(frame, _cleaning(), TEST_KEY_COLS)
        assert counts[f"dropped_missing_{TEST_TARGET}"] == 2
        assert counts["output_rows"] == counts["input_rows"] - 2
        assert cleaned[TEST_TARGET].notna().all()

    def test_is_stateless_over_its_input(self, synthetic_frame):
        # Cleaning must not mutate the caller's frame: the same raw frame is
        # re-cleaned in tests and notebooks all the time.
        before = synthetic_frame.copy()
        clean(synthetic_frame, _cleaning(), TEST_KEY_COLS)
        pd.testing.assert_frame_equal(synthetic_frame, before)


class TestEngineerFeatures:
    def test_adds_calendar_parts(self, synthetic_frame):
        out = engineer_features(
            synthetic_frame, FeatureEngineeringConfig(), TEST_DATE_COL
        )
        assert f"{TEST_DATE_COL}_month" in out.columns
        assert out[f"{TEST_DATE_COL}_month"].between(1, 12).all()

    def test_drops_configured_columns(self, synthetic_frame):
        out = engineer_features(
            synthetic_frame,
            FeatureEngineeringConfig(date_parts=False, drop_columns=["num_b"]),
            TEST_DATE_COL,
        )
        assert "num_b" not in out.columns


class TestDataPipeline:
    def _config(self, tmp_path, synthetic_frame, **overrides) -> DataPipelineConfig:
        raw = tmp_path / "raw.csv"
        synthetic_frame.to_csv(raw, index=False)
        base = {
            "raw_path": str(raw),
            "processed_path": str(tmp_path / "processed" / "model_input.parquet"),
            "checkpoint_dir": str(tmp_path / "processed"),
            "key_cols": TEST_KEY_COLS,
            "date_col": TEST_DATE_COL,
            "target": TEST_TARGET,
            "cleaning": _cleaning(),
            "mlflow": {"enabled": False},
        }
        return DataPipelineConfig(**{**base, **overrides})

    def test_output_carries_keys_and_target(self, tmp_path, synthetic_frame):
        config = self._config(tmp_path, synthetic_frame)
        processed = pd.read_parquet(DataPipeline(config).run())
        for column in [*TEST_KEY_COLS, TEST_TARGET]:
            assert column in processed.columns
        assert len(processed) == len(synthetic_frame)

    def test_writes_a_manifest_with_the_upstream_config(self, tmp_path, synthetic_frame):
        config = self._config(tmp_path, synthetic_frame)
        DataPipeline(config).run()

        manifest = load_manifest(config.processed_path)
        assert manifest["key_cols"] == TEST_KEY_COLS
        assert manifest["config"]["target"] == TEST_TARGET
        assert manifest["row_counts"]["output_rows"] == len(synthetic_frame)

    def test_ambiguous_keys_fail_loudly(self, tmp_path, synthetic_frame):
        # Duplicate keys that survive dedup (dedup off) would make split
        # membership ambiguous, so the output contract check must catch them.
        doubled = pd.concat([synthetic_frame, synthetic_frame.head(3)])
        config = self._config(tmp_path, doubled)
        config.cleaning.drop_duplicates = False
        with pytest.raises(ValueError, match="share a key"):
            DataPipeline(config).run()


class TestStageCheckpoints:
    def test_named_stages_are_piped_out(self, tmp_path, synthetic_frame):
        pipeline = TestDataPipeline()
        config = pipeline._config(
            tmp_path, synthetic_frame, checkpoints=["cleaned", "features"]
        )
        DataPipeline(config).run()

        checkpoints = tmp_path / "processed"
        assert (checkpoints / "cleaned.parquet").exists()
        assert (checkpoints / "features.parquet").exists()
        # The feature stage adds calendar parts, so the two differ - which is
        # the whole reason for keeping both.
        cleaned = pd.read_parquet(checkpoints / "cleaned.parquet")
        features = pd.read_parquet(checkpoints / "features.parquet")
        assert features.shape[1] > cleaned.shape[1]

    def test_unnamed_stages_are_not_written(self, tmp_path, synthetic_frame):
        config = TestDataPipeline()._config(tmp_path, synthetic_frame, checkpoints=[])
        DataPipeline(config).run()
        assert not (tmp_path / "processed" / "cleaned.parquet").exists()

    def test_manifest_records_which_stages_were_kept(self, tmp_path, synthetic_frame):
        config = TestDataPipeline()._config(
            tmp_path, synthetic_frame, checkpoints=["cleaned"]
        )
        DataPipeline(config).run()
        manifest = load_manifest(config.processed_path)
        assert set(manifest["stage_checkpoints"]) == {"cleaned"}
