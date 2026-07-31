"""Schema contract tests.

Scope: the CUSTOM validators and the warn-and-fill paths only. Built-in
pydantic behaviour (Literal narrowing, type coercion, required fields) is
pydantic's own test suite's job and is not re-tested here.
"""

import logging

import pytest
from pydantic import ValidationError

from PROJECT.schemas import (
    DataPipelineConfig,
    EvaluationConfig,
    InferenceConfig,
    TorchTrainerConfig,
    TrainingConfig,
    TrainingSplitConfig,
)


class TestDataPipelineConfig:
    def test_dropping_a_key_column_is_rejected(self):
        with pytest.raises(ValidationError, match="model-input table must"):
            DataPipelineConfig(
                key_cols=["entity_id"], features={"drop_columns": ["entity_id"]}
            )

    def test_dropping_the_target_is_rejected(self):
        with pytest.raises(ValidationError, match="model-input table must"):
            DataPipelineConfig(target="y", features={"drop_columns": ["y"]})

    def test_empty_key_cols_is_rejected(self):
        with pytest.raises(ValidationError, match="key_cols must not be empty"):
            DataPipelineConfig(key_cols=[])

    def test_processed_path_must_differ_from_raw(self):
        with pytest.raises(ValidationError, match="must differ from raw_path"):
            DataPipelineConfig(raw_path="data/x.parquet", processed_path="data/x.parquet")

    def test_unknown_checkpoint_stage_is_rejected(self):
        with pytest.raises(ValidationError, match="unknown stages"):
            DataPipelineConfig(checkpoints=["cleaned", "polished"])


class TestSplitConfig:
    def test_ratios_must_sum_to_one(self):
        # Inherited from core.config.SplitConfig; asserted here because the
        # composite is what the project actually instantiates.
        with pytest.raises(ValidationError, match="sum to 1.0"):
            TrainingSplitConfig(train_size=0.8, val_size=0.15, test_size=0.15)

    def test_temporal_mode_requires_a_time_column(self):
        with pytest.raises(ValidationError, match="requires split.time_col"):
            TrainingSplitConfig(mode="temporal", boundaries={"val_start": "2024-01-01"})

    def test_temporal_mode_requires_both_boundaries(self):
        with pytest.raises(ValidationError, match="requires boundaries"):
            TrainingSplitConfig(
                mode="temporal", time_col="date", boundaries={"val_start": "2024-01-01"}
            )


class TestTrainingConfig:
    def test_target_as_a_feature_is_rejected(self):
        with pytest.raises(ValidationError, match="label leakage"):
            TrainingConfig(target="y", numeric_features=["y", "x"])

    def test_column_declared_twice_is_rejected(self):
        with pytest.raises(ValidationError, match="numeric and categorical"):
            TrainingConfig(numeric_features=["x"], categorical_features=["x"])

    def test_split_key_cols_are_inherited_with_a_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            config = TrainingConfig(key_cols=["entity_id", "date"], split={})
        assert config.split.key_cols == ["entity_id", "date"]
        assert "inherited key_cols" in caplog.text

    def test_key_column_used_as_feature_warns_but_is_allowed(self, caplog):
        with caplog.at_level(logging.WARNING):
            config = TrainingConfig(
                key_cols=["entity_id"], numeric_features=["entity_id"]
            )
        assert config.numeric_features == ["entity_id"]
        assert "identify" in caplog.text

    def test_selection_metric_must_exist_for_the_task(self):
        with pytest.raises(ValidationError, match="is not produced"):
            TrainingConfig(task="regression", selection={"metric": "f1_macro"})

    def test_regression_rejects_a_stratified_split(self):
        with pytest.raises(ValidationError, match="categorical target"):
            TrainingConfig(
                task="regression",
                selection={"metric": "rmse", "mode": "min"},
                split={"mode": "stratified"},
            )


class TestTorchTrainerConfig:
    def test_subsample_fraction_is_bounded(self):
        with pytest.raises(ValidationError, match="subsample_frac"):
            TorchTrainerConfig(subsample_frac=1.5)

    def test_visible_devices_accepts_an_int_from_the_cli(self):
        assert TorchTrainerConfig(visible_devices=0).visible_devices == "0"


class TestInferenceConfig:
    def test_unsupported_output_extension_is_rejected(self):
        with pytest.raises(ValidationError, match="must end in .parquet or .csv"):
            InferenceConfig(output_path="outputs/predictions.txt")

    def test_explicit_timestamp_warns_that_use_is_ignored(self, caplog):
        with caplog.at_level(logging.WARNING):
            config = InferenceConfig(
                model={"use": "best", "timestamp": "20260101_000000"}
            )
        assert config.model.timestamp == "20260101_000000"
        assert "is ignored" in caplog.text

    def test_unquoted_cli_timestamp_is_rejected_with_the_fix(self):
        # Hydra reads 20260101_000000 as a numeric literal; silently coercing
        # it back to a string would look for the wrong run.
        with pytest.raises(ValidationError, match="Quote it"):
            InferenceConfig(model={"timestamp": 20260101000000})


class TestEvaluationConfig:
    def test_empty_key_cols_is_rejected(self):
        with pytest.raises(ValidationError, match="joined to ground truth by key"):
            EvaluationConfig(key_cols=[])

    def test_selection_metric_must_exist_for_the_task(self):
        with pytest.raises(ValidationError, match="is not produced"):
            EvaluationConfig(task="regression", selection_metric="accuracy")

    def test_negative_top_n_is_rejected(self):
        with pytest.raises(ValidationError, match="top_n"):
            EvaluationConfig(triage={"top_n": -1})
