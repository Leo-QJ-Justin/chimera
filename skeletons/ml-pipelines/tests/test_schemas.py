"""Schema contract tests.

Scope: the CUSTOM validators and the warn-and-fill paths only. Built-in
pydantic behaviour (Literal narrowing, type coercion, required fields) is
pydantic's own test suite's job and is not re-tested here.
"""

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from PROJECT.schemas import (
    ChoiceSpace,
    DataPipelineConfig,
    DiagnosticsConfig,
    EvaluationConfig,
    FloatSpace,
    InferenceConfig,
    IntSpace,
    PlotsConfig,
    ShapConfig,
    TorchTrainerConfig,
    TrainingConfig,
    TrainingSplitConfig,
    TuneConfig,
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

    def test_tune_metric_must_exist_for_the_task(self):
        # A project metric alias now, in the same vocabulary evaluate speaks -
        # which is also what catches a leftover sklearn scoring string.
        with pytest.raises(ValidationError, match="is not produced"):
            TrainingConfig(
                task="regression",
                selection={"metric": "rmse", "mode": "min"},
                split={"mode": "shuffle"},
                trainer={"tune": {"metric": "neg_root_mean_squared_error"}},
            )

    def test_regression_rejects_a_stratified_split(self):
        with pytest.raises(ValidationError, match="categorical target"):
            TrainingConfig(
                task="regression",
                selection={"metric": "rmse", "mode": "min"},
                split={"mode": "stratified"},
            )


class TestDiagnosticsAndPlotsConfig:
    """The knobs, and the guard against ``extra="ignore"`` eating a typo.

    Composite schemas ignore unknown sections by design (Hydra composition
    injects sections a pipeline does not use), which means a key that is in
    the shipped YAML but *not* in the model is dropped in silence and the
    switch it names does nothing. These compare the two directly.
    """

    def test_diagnostics_knobs_round_trip(self):
        config = TrainingConfig(
            diagnostics={
                "enabled": True,
                "shap": {"enabled": False, "sample_size": 50, "max_display": 5},
            }
        )
        assert config.diagnostics.enabled is True
        assert config.diagnostics.shap.enabled is False
        assert config.diagnostics.shap.sample_size == 50
        assert config.diagnostics.shap.max_display == 5

    def test_plots_knob_round_trips(self):
        assert EvaluationConfig(plots={"enabled": False}).plots.enabled is False

    def test_shipped_training_yaml_diagnostics_block_is_fully_understood(self):
        block = _shipped("training_pipeline", "training.yaml")["diagnostics"]
        assert set(block) == set(DiagnosticsConfig.model_fields)
        assert set(block["shap"]) == set(ShapConfig.model_fields)
        # And the values survive validation, not just the key names.
        assert TrainingConfig(diagnostics=block).diagnostics.model_dump() == block

    def test_shipped_evaluation_yaml_plots_block_is_fully_understood(self):
        block = _shipped("evaluation_pipeline", "evaluation.yaml")["plots"]
        assert set(block) == set(PlotsConfig.model_fields)
        assert EvaluationConfig(plots=block).plots.model_dump() == block

    def test_a_zero_shap_sample_is_rejected(self):
        with pytest.raises(ValidationError, match="sample_size"):
            TrainingConfig(diagnostics={"shap": {"sample_size": 0}})


def _shipped(pipeline: str, filename: str) -> dict:
    """A shipped pipeline config, read as plain YAML.

    The one place tests read `configs/` rather than schema defaults: the
    assertion *is* that the file and the schema agree, and it cannot be
    made from either side alone.
    """
    import yaml

    import PROJECT

    path = Path(PROJECT.__file__).parent / "pipelines" / pipeline / "configs" / filename
    return yaml.safe_load(path.read_text())


class TestTuneConfigSpaces:
    """``tune.space`` entries: which kind of range a dict becomes, and when.

    The union has to be unambiguous - a range typed into a config decides
    what a search does, and a float range silently read as an integer one
    would be a different search that still runs.
    """

    def test_each_shape_parses_as_its_own_kind(self):
        config = TuneConfig(
            space={
                "max_depth": {"low": 3, "high": 20},
                "learning_rate": {"low": 0.01, "high": 0.3, "log": True},
                "max_features": {"choices": ["sqrt", "log2", None]},
                "n_estimators": False,
            }
        )
        assert isinstance(config.space["max_depth"], IntSpace)
        assert isinstance(config.space["learning_rate"], FloatSpace)
        assert isinstance(config.space["max_features"], ChoiceSpace)
        # `false` is the disable switch, not a range with no fields.
        assert config.space["n_estimators"] is False

    def test_an_unknown_range_field_is_rejected(self):
        # extra="forbid" here, unlike the composite sections: nothing composes
        # keys into a range, so an unrecognised one is a typo that would
        # otherwise be dropped and searched as if it had never been written.
        with pytest.raises(ValidationError):
            TuneConfig(space={"max_depth": {"low": 3, "high": 20, "scale": "log"}})

    def test_a_log_scaled_integer_range_rejects_a_step(self):
        with pytest.raises(ValidationError, match="log=true"):
            IntSpace(low=1, high=100, step=5, log=True)

    def test_direction_defaults_to_unset_rather_than_maximize(self):
        # None means "infer from the metric"; a maximize default would make
        # `metric: rmse` search for the worst model in the space.
        assert TuneConfig().direction is None


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
