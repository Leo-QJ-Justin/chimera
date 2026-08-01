"""Evaluation pipeline: the join, the report, and the triage table.

Inputs come from a real inference run, not a hand-written predictions
file: the join contract is only meaningful if the two pipelines agree on
what a predictions file looks like.
"""

import json

import numpy as np
import pandas as pd
import pytest

from conftest import TEST_KEY_COLS, TEST_TARGET
from PROJECT.pipelines.evaluation_pipeline import EvaluationPipeline
from PROJECT.pipelines.evaluation_pipeline.modules.triage import (
    predicted_confidence,
    worst_cases,
)
from PROJECT.pipelines.inference_pipeline import InferencePipeline
from PROJECT.schemas import EvaluationConfig


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

        # The curve areas join the metric set rather than living in a second
        # one: report.json, the sidecar and MLflow must agree on what this
        # evaluation measured.
        assert set(report["metrics"]) == {"accuracy", "f1_macro", "roc_auc", "pr_auc"}
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
        # The training run behind this fixture is logreg, which pools
        # train+val - so the recorded number is a CV estimate, and the
        # report says so rather than implying a like-for-like delta.
        assert comparison["best_metric"] == "cv_f1_macro"
        assert comparison["best_basis"] == "k-fold CV estimate on train+val"
        assert comparison["delta"] == pytest.approx(
            comparison["evaluation_value"] - comparison["best_value"]
        )

    def test_a_changed_ground_truth_table_warns_and_still_reports(
        self, predictions, evaluation_config_factory, caplog
    ):
        """Scoring an old model on refreshed data is allowed, never silent.

        The training run recorded the content hash of the table it read, so
        the report can say the two are no longer the same population - and
        say it rather than refuse, because doing this deliberately is a
        legitimate thing to do.
        """
        import logging

        path, training_config = predictions
        table = pd.read_parquet(training_config.processed_path)
        table.loc[0, "num_a"] = table.loc[0, "num_a"] + 1.0
        table.to_parquet(training_config.processed_path, index=False)

        config = evaluation_config_factory(path, training_config)
        with caplog.at_level(logging.WARNING):
            run_dir = EvaluationPipeline(config).run()

        assert "different data than the model trained on" in caplog.text
        assert (run_dir / "report.json").exists()

    def test_comparison_is_skipped_when_no_best_exists(
        self, predictions, evaluation_config_factory, tmp_path
    ):
        path, training_config = predictions
        (tmp_path / "outputs" / "training" / "best.json").unlink()
        config = evaluation_config_factory(path, training_config)
        report = _report(config)
        assert "comparison" not in report


class TestPlots:
    """Prediction-based figures: what each input supports, and the switch."""

    def test_classification_gets_a_confusion_matrix_and_curves(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        run_dir = EvaluationPipeline(config).run()

        names = {p.name for p in (run_dir / "plots").iterdir()}
        assert {
            "confusion_matrix.png",
            "roc_curves.png",
            "pr_curves.png",
            "calibration_curve.png",
        } <= names

    def test_curve_areas_join_the_reported_metrics(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        report = _report(config)
        assert 0.0 <= report["metrics"]["roc_auc"] <= 1.0
        assert 0.0 <= report["metrics"]["pr_auc"] <= 1.0

    def test_the_markdown_report_links_the_images_it_wrote(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        run_dir = EvaluationPipeline(config).run()

        text = (run_dir / "report.md").read_text()
        assert "## Plots" in text
        assert "![confusion_matrix](plots/confusion_matrix.png)" in text
        # Links are relative to the report, so they resolve in the run dir
        # and in the MLflow artifact browser alike.
        for link in json.loads((run_dir / "report.json").read_text())["plots"]:
            assert (run_dir / link).exists()

    def test_without_probability_columns_only_the_matrix_is_drawn(
        self, predictions, evaluation_config_factory, tmp_path
    ):
        """The include_probabilities=false path, and it must say so."""
        path, training_config = predictions
        frame = pd.read_parquet(path)
        frame = frame.drop(columns=[c for c in frame.columns if c.startswith("proba_")])
        rewritten = tmp_path / "no_proba.parquet"
        frame.to_parquet(rewritten, index=False)

        config = evaluation_config_factory(rewritten, training_config)
        run_dir = EvaluationPipeline(config).run()

        names = {p.name for p in (run_dir / "plots").iterdir()}
        assert names == {"confusion_matrix.png"}
        report = json.loads((run_dir / "report.json").read_text())
        assert "roc_auc" not in report["metrics"]

    def test_regression_gets_residuals(self, tmp_path, evaluation_config_factory):
        frame = pd.DataFrame(
            {
                "entity_id": [f"e{i}" for i in range(30)],
                "date": pd.date_range("2024-01-01", periods=30),
                "target": np.linspace(0.0, 10.0, 30),
                "prediction": np.linspace(0.2, 9.5, 30),
            }
        )
        truth = tmp_path / "truth.parquet"
        preds = tmp_path / "regression_preds.parquet"
        frame.to_parquet(truth, index=False)
        frame.drop(columns=["target"]).to_parquet(preds, index=False)

        config = EvaluationConfig(
            predictions_path=str(preds),
            processed_path=str(truth),
            output_dir=str(tmp_path / "outputs" / "regression_evaluation"),
            task="regression",
            target=TEST_TARGET,
            key_cols=TEST_KEY_COLS,
            selection_metric="rmse",
            compare_to_best=False,
            mlflow={"enabled": False},
        )
        run_dir = EvaluationPipeline(config).run()
        assert (run_dir / "plots" / "residuals.png").exists()
        assert "![residuals](plots/residuals.png)" in (run_dir / "report.md").read_text()

    def test_the_kill_switch_writes_no_plots_and_no_section(
        self, predictions, evaluation_config_factory
    ):
        path, training_config = predictions
        config = evaluation_config_factory(
            path, training_config, plots={"enabled": False}
        )
        run_dir = EvaluationPipeline(config).run()

        assert not (run_dir / "plots").exists()
        assert "## Plots" not in (run_dir / "report.md").read_text()
        report = json.loads((run_dir / "report.json").read_text())
        assert "plots" not in report
        assert "roc_auc" not in report["metrics"]

    def test_a_failing_plot_costs_the_report_nothing_else(
        self, predictions, evaluation_config_factory, monkeypatch
    ):
        from PROJECT.pipelines.evaluation_pipeline.modules import diagnostics

        def explode(*args, **kwargs):
            raise RuntimeError("plot exploded")

        monkeypatch.setattr(diagnostics, "plot_confusion_matrix", explode)
        path, training_config = predictions
        config = evaluation_config_factory(path, training_config)
        run_dir = EvaluationPipeline(config).run()

        assert (run_dir / "report.json").exists()
        names = {p.name for p in (run_dir / "plots").iterdir()}
        assert "confusion_matrix.png" not in names
        # The curves are drawn by separate, separately guarded calls.
        assert "roc_curves.png" in names


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
