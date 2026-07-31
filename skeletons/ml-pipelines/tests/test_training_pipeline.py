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
    TEST_KEY_COLS,
    TEST_TARGET,
    TORCH_TRAINER,
    XGBOOST_TRAINER,
    make_training_config,
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
        assert {"splits.json", "metadata.json", "config.yaml", "metrics.jsonl"} <= names
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
