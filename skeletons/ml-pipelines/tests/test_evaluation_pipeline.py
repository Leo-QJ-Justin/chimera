"""Evaluation pipeline: the join, the report, and the triage table.

Inputs come from a real inference run, not a hand-written predictions
file: the join contract is only meaningful if the two pipelines agree on
what a predictions file looks like.
"""

import json

import pandas as pd
import pytest

from conftest import TEST_KEY_COLS, TEST_TARGET
from PROJECT.pipelines.evaluation_pipeline import EvaluationPipeline
from PROJECT.pipelines.evaluation_pipeline.modules.triage import (
    predicted_confidence,
    worst_cases,
)
from PROJECT.pipelines.inference_pipeline import InferencePipeline


def _report(config) -> dict:
    """Run the pipeline and read back its JSON report."""
    run_dir = EvaluationPipeline(config).run()
    return json.loads((run_dir / "report.json").read_text())


@pytest.fixture
def predictions(trained_run, inference_config_factory):
    """A real predictions file plus the training config behind it."""
    _, training_config = trained_run
    config = inference_config_factory(training_config)
    return InferencePipeline(config).run(), training_config


class TestReport:
    def test_writes_both_report_formats(self, predictions, evaluation_config_factory):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        run_dir = EvaluationPipeline(config).run()

        assert (run_dir / "report.json").exists()
        assert (run_dir / "report.md").exists()
        assert "# Evaluation report" in (run_dir / "report.md").read_text()

    def test_metrics_match_the_project_definitions(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        report = _report(config)

        assert set(report["metrics"]) == {"accuracy", "f1_macro"}
        assert 0.0 <= report["metrics"]["f1_macro"] <= 1.0
        assert (
            report["error_summary"]["n_rows"]
            == report["error_summary"]["n_correct"] + report["error_summary"]["n_wrong"]
        )

    def test_per_class_table_is_included_for_classification(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        report = _report(config)
        classes = {row["class"] for row in report["per_class"]}
        assert {"0", "1"} <= classes

    def test_compares_against_the_recorded_best(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        report = _report(config)

        comparison = report["comparison"]
        assert comparison["best_metric"] == "val_f1_macro"
        assert comparison["delta"] == pytest.approx(
            comparison["evaluation_value"] - comparison["best_value"]
        )

    def test_comparison_is_skipped_when_no_best_exists(
        self, predictions, evaluation_config_factory, tmp_path
    ):
        path, training_config = predictions
        (tmp_path / "outputs" / "training" / "best.json").unlink()
        config = evaluation_config_factory(path, training_config)
        report = _report(config)
        assert "comparison" not in report


class TestJoin:
    def test_unjoinable_predictions_fail_loudly(
        self, predictions, evaluation_config_factory, tmp_path
    ):
        path, training_config = predictions
        frame = pd.read_parquet(path)
        frame[TEST_KEY_COLS[0]] = "no-such-entity"
        rewritten = tmp_path / "unjoinable.parquet"
        frame.to_parquet(rewritten, index=False)

        config = evaluation_config_factory(rewritten, training_config)
        with pytest.raises(ValueError, match="share no keys"):
            EvaluationPipeline(config).run()

    def test_missing_prediction_column_fails_loudly(
        self, predictions, evaluation_config_factory, tmp_path
    ):
        path, training_config = predictions
        frame = pd.read_parquet(path).drop(columns=["prediction"])
        rewritten = tmp_path / "no_prediction.parquet"
        frame.to_parquet(rewritten, index=False)

        config = evaluation_config_factory(rewritten, training_config)
        with pytest.raises(KeyError, match="prediction"):
            EvaluationPipeline(config).run()

    def test_duplicate_ground_truth_keys_fail_loudly(
        self, predictions, evaluation_config_factory, tmp_path
    ):
        path, training_config = predictions
        table = pd.read_parquet(training_config.processed_path)
        doubled = tmp_path / "doubled.parquet"
        pd.concat([table, table.head(3)]).to_parquet(doubled, index=False)

        config = evaluation_config_factory(
            path, training_config, processed_path=str(doubled)
        )
        with pytest.raises(ValueError, match="duplicate"):
            EvaluationPipeline(config).run()


class TestTriage:
    def test_triage_lists_only_wrong_rows_worst_first(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        report = _report(config)

        rows = report["triage"]
        assert len(rows) <= config.triage.top_n
        assert all(row[TEST_TARGET] != row["prediction"] for row in rows)
        confidences = [row["confidence"] for row in rows]
        assert confidences == sorted(confidences, reverse=True)

    def test_drill_down_columns_are_carried(self, predictions, evaluation_config_factory):
        path, training_config = predictions
        config = evaluation_config_factory(
            path, training_config, triage={"top_n": 5, "drill_down_columns": ["cat_a"]}
        )
        report = _report(config)
        assert all("cat_a" in row for row in report["triage"])

    def test_top_n_zero_produces_an_empty_table(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config, triage={"top_n": 0})
        report = _report(config)
        assert report["triage"] == []

    def test_regression_triage_ranks_by_absolute_error(self):
        frame = pd.DataFrame(
            {
                "entity_id": ["a", "b", "c"],
                "date": ["2024-01-01"] * 3,
                "target": [1.0, 2.0, 3.0],
                "prediction": [1.1, 9.0, 3.05],
            }
        )
        ranked = worst_cases(
            frame, "target", "prediction", "regression", 2, ["entity_id", "date"]
        )
        assert ranked["entity_id"].tolist() == ["b", "a"]
        assert ranked["residual"].iloc[0] == pytest.approx(-7.0)

    def test_confidence_is_nan_without_probability_columns(self):
        frame = pd.DataFrame({"prediction": [0, 1]})
        assert predicted_confidence(frame, "prediction").isna().all()
