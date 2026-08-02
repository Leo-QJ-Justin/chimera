"""Inference pipeline: it loads exactly what training saved.

These tests consume the ``trained_run`` fixture rather than a hand-built
model directory - the point of the contract is that the two pipelines
agree, which a fabricated metadata.json would not prove.
"""

import pandas as pd
import pytest

from conftest import TEST_KEY_COLS, make_training_config, trainer_params
from PROJECT.core.run_artifacts import load_metadata
from PROJECT.pipelines.inference_pipeline import InferencePipeline
from PROJECT.pipelines.training_pipeline import TrainingPipeline


class TestPredictions:
    def test_predicts_one_row_per_input_row(self, trained_run, inference_config_factory):
        _, training_config = trained_run
        config = inference_config_factory(training_config)

        predictions = pd.read_parquet(InferencePipeline(config).run())
        source = pd.read_parquet(training_config.processed_path)
        assert len(predictions) == len(source)
        assert "prediction" in predictions.columns
        assert set(TEST_KEY_COLS) <= set(predictions.columns)

    def test_probability_columns_follow_the_model_classes(
        self, trained_run, inference_config_factory
    ):
        _, training_config = trained_run
        config = inference_config_factory(training_config, include_probabilities=True)
        predictions = pd.read_parquet(InferencePipeline(config).run())
        proba_cols = [c for c in predictions.columns if c.startswith("proba_")]
        assert len(proba_cols) == 2
        assert predictions[proba_cols].sum(axis=1).round(6).eq(1.0).all()

    def test_csv_output_is_supported(
        self, trained_run, inference_config_factory, tmp_path
    ):
        _, training_config = trained_run
        config = inference_config_factory(
            training_config, output_path=str(tmp_path / "p.csv")
        )
        assert len(pd.read_csv(InferencePipeline(config).run())) > 0


class TestFeatureContract:
    def test_missing_feature_column_raises(
        self, trained_run, inference_config_factory, tmp_path
    ):
        run_dir, training_config = trained_run
        feature = load_metadata(run_dir)["feature_columns"][0]
        source = pd.read_parquet(training_config.processed_path)
        truncated = source.drop(columns=[feature])
        input_path = tmp_path / "truncated.parquet"
        truncated.to_parquet(input_path, index=False)

        config = inference_config_factory(training_config, input_path=str(input_path))
        with pytest.raises(ValueError, match="missing 1 feature column"):
            InferencePipeline(config).run()

    def test_column_order_is_restored_from_metadata(
        self, trained_run, inference_config_factory, tmp_path
    ):
        _, training_config = trained_run
        source = pd.read_parquet(training_config.processed_path)

        baseline = inference_config_factory(training_config)
        expected = pd.read_parquet(InferencePipeline(baseline).run())["prediction"]

        shuffled = source[list(reversed(source.columns))]
        input_path = tmp_path / "shuffled.parquet"
        shuffled.to_parquet(input_path, index=False)
        config = inference_config_factory(
            training_config,
            input_path=str(input_path),
            output_path=str(tmp_path / "shuffled_predictions.parquet"),
        )
        actual = pd.read_parquet(InferencePipeline(config).run())["prediction"]
        assert actual.tolist() == expected.tolist()


class TestRunSelection:
    def test_latest_resolves_when_best_is_absent(
        self, trained_run, inference_config_factory
    ):
        run_dir, training_config = trained_run
        (run_dir.parent / "best.json").unlink()
        # Falls back to latest.json, loudly (see ModelLoader.resolve_run_dir).
        config = inference_config_factory(training_config)
        assert InferencePipeline(config).run().exists()

    def test_explicit_timestamp_wins(self, trained_run, inference_config_factory):
        run_dir, training_config = trained_run
        config = inference_config_factory(
            training_config,
            model={
                "use": "latest",
                "timestamp": run_dir.name,
                "runs_dir": training_config.output_dir,
            },
        )
        assert InferencePipeline(config).run().exists()

    def test_unknown_timestamp_raises(self, trained_run, inference_config_factory):
        _, training_config = trained_run
        config = inference_config_factory(
            training_config,
            model={
                "use": "latest",
                "timestamp": "19990101_000000",
                "runs_dir": training_config.output_dir,
            },
        )
        with pytest.raises(FileNotFoundError):
            InferencePipeline(config).run()


class TestTrainerAgnosticLoading:
    """Every family reloads through the same registry path."""

    @pytest.mark.parametrize("trainer", trainer_params())
    def test_any_trainers_run_serves(
        self, tmp_path, processed_file, trainer, inference_config_factory
    ):
        training_config = make_training_config(tmp_path, processed_file, trainer)
        TrainingPipeline(training_config).run()

        config = inference_config_factory(
            training_config, output_path=str(tmp_path / f"{trainer['kind']}.parquet")
        )
        predictions = pd.read_parquet(InferencePipeline(config).run())
        assert len(predictions) == len(pd.read_parquet(processed_file))
        assert predictions["prediction"].notna().all()
