"""Training pipeline end-to-end on tmp_path, tracking disabled.

MLflow is neutralised declaratively (``mlflow.enabled=false`` in the
fixture config) rather than by monkeypatching: that is the same switch
production uses, so the test exercises the shipped code path.
"""

import json

import pandas as pd
import pytest

from conftest import (
    LIGHTGBM_TRAINER,
    LOGREG_TRAINER,
    RANDOM_FOREST_TRAINER,
    TEST_KEY_COLS,
    TEST_TARGET,
    TORCH_TRAINER,
    XGBOOST_TRAINER,
    make_training_config,
    needs,
    needs_trainer,
    trainer_params,
)
from PROJECT.core.run_artifacts import (
    get_best_info,
    load_metadata,
    resolve_artifact_path,
)
from PROJECT.core.splits import load_splits
from PROJECT.pipelines.training_pipeline import TrainingPipeline


class TestRunArtifacts:
    def test_run_dir_is_self_describing(self, trained_run):
        run_dir, _ = trained_run
        names = {p.name for p in run_dir.iterdir()}
        assert {
            "splits.json",
            "metadata.json",
            "config.yaml",
            "metrics.jsonl",
            "plots",
        } <= names
        # Whatever the trainer saved is named in metadata, never guessed.
        for filename in load_metadata(run_dir)["files"].values():
            assert (run_dir / filename).exists()

    def test_config_snapshot_records_what_ran(self, trained_run):
        import yaml

        run_dir, config = trained_run
        snapshot = yaml.safe_load((run_dir / "config.yaml").read_text())
        assert snapshot["processed_path"] == config.processed_path
        assert snapshot["trainer"]["kind"] == config.trainer.kind
        assert snapshot["seed"] == config.seed

    def test_metadata_pins_the_feature_contract(self, trained_run):
        run_dir, config = trained_run
        metadata = load_metadata(run_dir)
        assert metadata["target_columns"] == [config.target]
        assert metadata["feature_columns"]
        # Keys and target are never features.
        assert not set(metadata["feature_columns"]) & {*TEST_KEY_COLS, TEST_TARGET}

    def test_metadata_carries_the_trainer_spec_for_reload(self, trained_run):
        run_dir, config = trained_run
        spec = load_metadata(run_dir)["hyperparameters"]
        assert spec["model_class"] == "LogisticRegressionTrainer"
        assert spec["trainer"] == config.trainer.kind
        assert spec["cv_mode"] == config.split.mode

    def test_metrics_sidecar_is_written_without_mlflow(self, trained_run):
        run_dir, _ = trained_run
        records = [
            json.loads(line)
            for line in (run_dir / "metrics.jsonl").read_text().splitlines()
        ]
        logged = {k for r in records if r["type"] == "metrics" for k in r["metrics"]}
        assert {"val_f1_macro", "test_f1_macro"} <= logged


class TestSplits:
    def test_membership_is_recorded_with_fingerprints(self, trained_run):
        run_dir, config = trained_run
        payload = load_splits(run_dir)
        assert payload["key_cols"] == config.split.key_cols
        assert set(payload["splits"]) == {"train", "val", "test"}
        assert all(len(fp) == 16 for fp in payload["fingerprints"].values())

    def test_splits_partition_the_input_table(self, trained_run):
        run_dir, config = trained_run
        payload = load_splits(run_dir)
        table = pd.read_parquet(config.processed_path)
        members = [k for keys in payload["splits"].values() for k in keys]
        assert len(members) == len(set(members)) == len(table)

    def test_same_seed_reproduces_the_same_fingerprints(self, training_config, tmp_path):
        # Separate output dirs, not two runs into one: the run timestamp is
        # second-granular and core.make_run_dir refuses a collision, which is
        # the behaviour test_core_run_artifacts asserts.
        second_config = training_config.model_copy(
            update={"output_dir": str(tmp_path / "outputs" / "training_again")}
        )
        first = load_splits(TrainingPipeline(training_config).run())
        second = load_splits(TrainingPipeline(second_config).run())
        assert first["fingerprints"] == second["fingerprints"]


class TestPointers:
    def test_latest_and_best_resolve_to_the_run(self, trained_run):
        run_dir, config = trained_run
        assert resolve_artifact_path(config.output_dir) == run_dir
        best = get_best_info(config.output_dir)
        assert best["timestamp"] == run_dir.name
        assert best["metric"] == "val_f1_macro"


class TestTemporalSplit:
    def test_temporal_mode_splits_on_the_boundaries(self, training_config):
        training_config.split.mode = "temporal"
        training_config.split.time_col = "date"
        training_config.split.boundaries = {
            "val_start": "2024-03-01",
            "test_start": "2024-04-01",
        }
        payload = load_splits(TrainingPipeline(training_config).run())
        val_dates = [key.split("|")[1] for key in payload["splits"]["val"]]
        assert all("2024-03" <= d[:7] < "2024-04" for d in val_dates)

    def test_impossible_boundaries_fail_loudly(self, training_config):
        training_config.split.mode = "temporal"
        training_config.split.time_col = "date"
        training_config.split.boundaries = {
            "val_start": "2030-01-01",
            "test_start": "2030-06-01",
        }
        with pytest.raises(ValueError, match="empty"):
            TrainingPipeline(training_config).run()


class TestTrainerSwap:
    """The orchestrator must not care which family it got."""

    @pytest.mark.parametrize("trainer", trainer_params())
    def test_every_trainer_produces_the_same_artifact_shape(
        self, tmp_path, processed_file, trainer
    ):
        config = make_training_config(tmp_path, processed_file, trainer)
        run_dir = TrainingPipeline(config).run()

        metadata = load_metadata(run_dir)
        assert metadata["model_type"] == trainer["kind"]
        assert (run_dir / "splits.json").exists()
        # Whatever this family saved is named in metadata, never guessed.
        for filename in metadata["files"].values():
            assert (run_dir / filename).exists()
        assert get_best_info(config.output_dir)["metric"] == "val_f1_macro"

    @needs_trainer("torch")
    def test_torch_history_reaches_the_metrics_sidecar(self, tmp_path, processed_file):
        config = make_training_config(tmp_path, processed_file, TORCH_TRAINER)
        run_dir = TrainingPipeline(config).run()

        records = [
            json.loads(line)
            for line in (run_dir / "metrics.jsonl").read_text().splitlines()
        ]
        # Per-epoch records carry a step; the final metric set does not.
        assert any(r.get("step") is not None for r in records if r["type"] == "metrics")
        assert load_metadata(run_dir)["training_info"]["trainer"]["history"]


class TestDiagnostics:
    """Post-fit figures: what each family can produce, and the kill switch."""

    def _plots(self, tmp_path, processed_file, trainer, **overrides) -> tuple:
        config = make_training_config(tmp_path, processed_file, trainer, **overrides)
        run_dir = TrainingPipeline(config).run()
        plots_dir = run_dir / "plots"
        names = {p.name for p in plots_dir.iterdir()} if plots_dir.exists() else set()
        return run_dir, plots_dir, names

    def test_a_one_shot_fit_gets_importances_but_no_curves(
        self, tmp_path, processed_file
    ):
        # Random forest has no iterations to plot and no history to draw one
        # from, which is a skipped step rather than a failure.
        _, plots_dir, names = self._plots(
            tmp_path,
            processed_file,
            RANDOM_FOREST_TRAINER,
            diagnostics={"shap": {"enabled": False}},
        )
        assert {"feature_importances.png", "feature_importances.csv"} <= names
        assert "training_curves.png" not in names

        rows = pd.read_csv(plots_dir / "feature_importances.csv")
        assert list(rows.columns) == ["feature", "importance"]
        # One row per *transformed* column: one-hot encoding makes that a
        # different count from the raw feature list.
        assert len(rows) >= 3
        assert rows["importance"].abs().is_monotonic_decreasing

    def test_coefficients_are_charted_for_a_linear_family(
        self, tmp_path, processed_file
    ):
        _, _, names = self._plots(
            tmp_path,
            processed_file,
            LOGREG_TRAINER,
            diagnostics={"shap": {"enabled": False}},
        )
        assert "feature_importances.png" in names

    @needs_trainer("torch")
    def test_torch_gets_curves_and_no_attribution_chart(self, tmp_path, processed_file):
        _, _, names = self._plots(tmp_path, processed_file, TORCH_TRAINER)
        assert "training_curves.png" in names
        # Documented skip: gradient attributions for an MLP are a different
        # tool, not a variant of feature_importances_.
        assert "feature_importances.png" not in names
        assert "shap_beeswarm.png" not in names

    @needs_trainer("lightgbm")
    def test_a_booster_gets_curves_from_its_captured_eval_record(
        self, tmp_path, processed_file
    ):
        run_dir, _, names = self._plots(
            tmp_path,
            processed_file,
            LIGHTGBM_TRAINER,
            diagnostics={"shap": {"enabled": False}},
        )
        assert {"training_curves.png", "feature_importances.png"} <= names

        # The same capture also reaches the sidecar step-wise, which is what
        # makes the curve recoverable without a tracking server.
        records = [
            json.loads(line)
            for line in (run_dir / "metrics.jsonl").read_text().splitlines()
        ]
        stepped = [
            r for r in records if r["type"] == "metrics" and r.get("step") is not None
        ]
        assert stepped, "no step-wise metric rows for a booster run"
        assert [r["step"] for r in stepped] == list(range(len(stepped)))
        assert all(any(k.startswith("val_") for k in r["metrics"]) for r in stepped)

    def test_the_kill_switch_writes_no_plots_at_all(self, tmp_path, processed_file):
        _, plots_dir, _ = self._plots(
            tmp_path,
            processed_file,
            RANDOM_FOREST_TRAINER,
            diagnostics={"enabled": False},
        )
        assert not plots_dir.exists()

    def test_a_failing_diagnostic_costs_the_run_nothing_else(
        self, tmp_path, processed_file, monkeypatch
    ):
        """One broken figure must not cost the run its artifacts."""
        from PROJECT.pipelines.training_pipeline.modules import diagnostics

        def explode(*args, **kwargs):
            raise RuntimeError("plot exploded")

        monkeypatch.setattr(diagnostics, "plot_feature_importances", explode)
        run_dir, _, names = self._plots(
            tmp_path,
            processed_file,
            RANDOM_FOREST_TRAINER,
            diagnostics={"shap": {"enabled": False}},
        )
        assert (run_dir / "metadata.json").exists()
        assert (run_dir / "model.joblib").exists()
        assert "feature_importances.png" not in names

    @needs("shap", reason="the 'explain' extra")
    def test_shap_summaries_are_written_when_the_extra_is_installed(
        self, tmp_path, processed_file
    ):
        _, _, names = self._plots(
            tmp_path,
            processed_file,
            RANDOM_FOREST_TRAINER,
            diagnostics={"shap": {"enabled": True, "sample_size": 30, "max_display": 5}},
        )
        assert {"shap_beeswarm.png", "shap_bar.png"} <= names

    def test_a_missing_shap_install_logs_and_skips(
        self, tmp_path, processed_file, monkeypatch, caplog
    ):
        """The optional-extra path, exercised whether or not shap is present."""
        import logging

        from PROJECT.pipelines.training_pipeline.modules import diagnostics

        monkeypatch.setattr(diagnostics, "_import_shap", lambda: None)
        with caplog.at_level(logging.INFO):
            _, _, names = self._plots(
                tmp_path, processed_file, RANDOM_FOREST_TRAINER
            )
        assert "shap_beeswarm.png" not in names
        # The rest of the diagnostics are unaffected.
        assert "feature_importances.png" in names

    def test_shap_can_be_disabled_on_its_own(self, tmp_path, processed_file, caplog):
        import logging

        with caplog.at_level(logging.INFO):
            _, _, names = self._plots(
                tmp_path,
                processed_file,
                RANDOM_FOREST_TRAINER,
                diagnostics={"shap": {"enabled": False}},
            )
        assert "shap_beeswarm.png" not in names
        assert "diagnostics.shap.enabled=false" in caplog.text


class TestTuning:
    @pytest.mark.parametrize(
        "base",
        [
            pytest.param(LOGREG_TRAINER, id="logreg"),
            pytest.param(
                LIGHTGBM_TRAINER, id="lightgbm", marks=needs_trainer("lightgbm")
            ),
            pytest.param(XGBOOST_TRAINER, id="xgboost", marks=needs_trainer("xgboost")),
        ],
    )
    def test_tuned_run_records_its_winners(self, tmp_path, processed_file, base):
        pytest.importorskip("optuna", reason="needs the 'tune' extra")
        trainer = {**base, "tune": {"enabled": True, "n_trials": 2, "cv": 2}}
        config = make_training_config(tmp_path, processed_file, trainer)
        run_dir = TrainingPipeline(config).run()

        spec = load_metadata(run_dir)["hyperparameters"]
        assert spec["best_params"]
        # The winners were folded into params, so a reload rebuilds the tuned
        # model rather than the configured one.
        for key, value in spec["best_params"].items():
            assert spec["params"][key] == value
