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
    file_fingerprint,
    get_best_info,
    load_metadata,
    resolve_artifact_path,
    save_best_pointer,
)
from PROJECT.core.splits import load_splits
from PROJECT.pipelines.training_pipeline import TrainingPipeline, get_trainer_class


def _sidecar_metrics(run_dir) -> set[str]:
    """Every metric key the run wrote to ``metrics.jsonl``."""
    records = [
        json.loads(line) for line in (run_dir / "metrics.jsonl").read_text().splitlines()
    ]
    return {k for r in records if r["type"] == "metrics" for k in r["metrics"]}


def _spy_on_tuning(monkeypatch, kind: str) -> dict:
    """Record how many rows the search was handed, then run it for real.

    Patched on the family's own class, because that is where a tuner lives
    now - the base only declares the signature.
    """
    seen: dict = {}
    trainer_cls = get_trainer_class(kind)
    original = trainer_cls.hyperparameter_tune

    def spy(self, X, y, **kwargs):
        seen["rows"] = len(X)
        return original(self, X, y, **kwargs)

    monkeypatch.setattr(trainer_cls, "hyperparameter_tune", spy)
    return seen


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

    def test_metadata_pins_the_data_the_run_actually_read(self, trained_run):
        run_dir, config = trained_run
        info = load_metadata(run_dir)["training_info"]
        assert info["processed_path"] == config.processed_path
        # Hashed from the file, so "same path" and "same table" stay two
        # separate questions.
        assert info["processed_fingerprint"] == file_fingerprint(config.processed_path)

    def test_the_environment_the_run_ran_under_is_recorded(self, trained_run):
        run_dir, _ = trained_run
        recorded = json.loads((run_dir / "environment.json").read_text())
        assert recorded["python"]
        # The one library every family's run goes through, whichever it built.
        assert "scikit-learn" in recorded["packages"]

    def test_metrics_sidecar_is_written_without_mlflow(self, trained_run):
        run_dir, _ = trained_run
        # logreg pools train+val, so its metric set is dev_/test_/cv_ (see
        # TestProtocols); what this asserts is that the sidecar receives it
        # with tracking off.
        logged = _sidecar_metrics(run_dir)
        assert {"dev_f1_macro", "test_f1_macro", "cv_f1_macro"} <= logged


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
        # logreg pools train+val, so its selection number is the CV estimate.
        assert best["metric"] == "cv_f1_macro"

    def test_a_protocol_switch_warns_instead_of_losing_the_run(
        self, tmp_path, processed_file, caplog
    ):
        """Two protocols in one output dir: the run survives, best.json holds.

        ``save_best_pointer`` refuses to rank a ``cv_`` value against a
        ``val_`` one - they estimate different things. That refusal arrives
        after the fit, so it must not cost the run the artifacts it wrote.
        """
        import logging

        config = make_training_config(tmp_path, processed_file, LOGREG_TRAINER)
        # A standing-val run's pointer, as a booster family would have left it.
        save_best_pointer(
            config.output_dir, "20260101_000000", 0.9, "val_f1_macro", "max"
        )
        with caplog.at_level(logging.WARNING):
            run_dir = TrainingPipeline(config).run()

        assert (run_dir / "metadata.json").exists()
        assert "best.json left unchanged" in caplog.text
        best = get_best_info(config.output_dir)
        assert (best["metric"], best["timestamp"]) == ("val_f1_macro", "20260101_000000")
        # latest.json still resolves to the run that was just written.
        assert resolve_artifact_path(config.output_dir) == run_dir


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
        # best.json is written either way; which number it holds is the
        # family's protocol, asserted in TestProtocols.
        expected = (
            "val_f1_macro"
            if get_trainer_class(trainer["kind"]).uses_val_in_fit
            else "cv_f1_macro"
        )
        assert get_best_info(config.output_dir)["metric"] == expected

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


class TestProtocols:
    """Per-family tuning/selection protocol (R1.10), asserted on both sides.

    The pooled protocol is not "the sklearn families do something else": it
    is what a family that never reads val during the fit is entitled to
    claim. So the assertions are about the numbers a run publishes, not
    about which class produced them.
    """

    def _run(self, tmp_path, processed_file, trainer, **overrides):
        config = make_training_config(tmp_path, processed_file, trainer, **overrides)
        run_dir = TrainingPipeline(config).run()
        return run_dir, config

    def _pool_size(self, run_dir) -> int:
        splits = load_splits(run_dir)["splits"]
        return len(splits["train"]) + len(splits["val"])

    # ------------------------------------------------------------- pooled (A)

    def test_a_pooled_family_fits_on_train_plus_val(self, tmp_path, processed_file):
        run_dir, _ = self._run(tmp_path, processed_file, RANDOM_FOREST_TRAINER)
        info = load_metadata(run_dir)["training_info"]

        assert info["fit_splits"] == ["train", "val"]
        assert info["n_fit_rows"] == self._pool_size(run_dir)
        # The tracker sees the same number, so a run is readable without
        # opening metadata.json.
        params = [
            json.loads(line)
            for line in (run_dir / "metrics.jsonl").read_text().splitlines()
            if json.loads(line)["type"] == "params"
        ]
        assert params[0]["params"]["n_fit"] == info["n_fit_rows"]

    def test_a_pooled_family_publishes_no_val_metric(self, tmp_path, processed_file):
        run_dir, _ = self._run(tmp_path, processed_file, RANDOM_FOREST_TRAINER)
        logged = _sidecar_metrics(run_dir)

        assert {"dev_accuracy", "dev_f1_macro", "test_f1_macro", "cv_f1_macro"} <= logged
        # val rows are inside the fit; a "val" score would read as held-out.
        assert not [k for k in logged if k.startswith("val_")]
        # dev_ replaces train_ for the pool: one in-sample name, not two.
        assert not [k for k in logged if k.startswith("train_")]

    def test_selection_is_the_cv_estimate_on_the_pool(self, tmp_path, processed_file):
        run_dir, config = self._run(tmp_path, processed_file, RANDOM_FOREST_TRAINER)
        info = load_metadata(run_dir)["training_info"]
        best = get_best_info(config.output_dir)

        assert info["selection_basis"] == "cv"
        assert best["metric"] == "cv_f1_macro"
        assert best["value"] == info["metrics"]["cv_f1_macro"]
        # The CV estimate is its own number, not the in-sample one relabelled.
        assert best["value"] != info["metrics"]["dev_f1_macro"]
        assert f"cv_{config.selection.metric}_std" in info["metrics"]

    def test_pooling_does_not_change_what_splits_json_records(
        self, tmp_path, processed_file
    ):
        """The pool is built at fit time; membership is still all three splits."""
        run_dir, config = self._run(tmp_path, processed_file, RANDOM_FOREST_TRAINER)
        payload = load_splits(run_dir)

        assert set(payload["splits"]) == {"train", "val", "test"}
        table = pd.read_parquet(config.processed_path)
        members = [k for keys in payload["splits"].values() for k in keys]
        assert len(members) == len(set(members)) == len(table)

    def test_a_pooled_search_folds_over_the_pool(
        self, tmp_path, processed_file, monkeypatch
    ):
        """The tuner is handed the pool, which is the whole point of R1.10."""
        pytest.importorskip("optuna", reason="needs the 'tune' extra")
        searched = _spy_on_tuning(monkeypatch, "random_forest")
        trainer = {
            **RANDOM_FOREST_TRAINER,
            "tune": {"enabled": True, "n_trials": 2, "cv": 2},
        }
        run_dir, _ = self._run(tmp_path, processed_file, trainer)

        assert searched["rows"] == self._pool_size(run_dir)

    # ------------------------------------------------------ standing val (B)

    @needs_trainer("lightgbm")
    def test_a_standing_val_family_is_unchanged(self, tmp_path, processed_file):
        run_dir, config = self._run(tmp_path, processed_file, LIGHTGBM_TRAINER)
        info = load_metadata(run_dir)["training_info"]
        logged = _sidecar_metrics(run_dir)

        assert {"train_f1_macro", "val_f1_macro", "test_f1_macro"} <= logged
        assert not [k for k in logged if k.startswith("cv_")]
        assert info["selection_basis"] == "val"
        assert info["fit_splits"] == ["train"]
        assert info["n_fit_rows"] == len(load_splits(run_dir)["splits"]["train"])
        assert get_best_info(config.output_dir)["metric"] == "val_f1_macro"

    @needs_trainer("lightgbm")
    def test_a_standing_val_search_folds_within_train(
        self, tmp_path, processed_file, monkeypatch
    ):
        pytest.importorskip("optuna", reason="needs the 'tune' extra")
        searched = _spy_on_tuning(monkeypatch, "lightgbm")
        trainer = {**LIGHTGBM_TRAINER, "tune": {"enabled": True, "n_trials": 2, "cv": 2}}
        run_dir, _ = self._run(tmp_path, processed_file, trainer)

        assert searched["rows"] == len(load_splits(run_dir)["splits"]["train"])


class TestCrossComparableSelection:
    """``selection.basis: cv`` (R1.11): one yardstick for every family.

    The default (``auto``) is R1.10's per-family behaviour, asserted above.
    What this class asserts is the opt-in: a standing-val family keeps the
    fit its early stopping needs *and* publishes the same CV number a pooled
    family does, so the two rank in one output dir without touching test.
    """

    @needs_trainer("lightgbm")
    def test_a_standing_val_family_keeps_its_fit_and_selects_on_cv(
        self, tmp_path, processed_file
    ):
        config = make_training_config(
            tmp_path, processed_file, LIGHTGBM_TRAINER, selection={"basis": "cv"}
        )
        run_dir = TrainingPipeline(config).run()
        info = load_metadata(run_dir)["training_info"]
        logged = _sidecar_metrics(run_dir)
        best = get_best_info(config.output_dir)

        # The shipped fit is untouched: train only, val still the referee.
        assert info["fit_splits"] == ["train"]
        assert info["n_fit_rows"] == len(load_splits(run_dir)["splits"]["train"])
        assert {"train_f1_macro", "val_f1_macro", "test_f1_macro"} <= logged
        # The selection number is the procedure-CV estimate on train+val.
        assert info["selection_basis"] == "cv"
        assert best["metric"] == "cv_f1_macro"
        assert best["value"] == info["metrics"]["cv_f1_macro"]
        assert f"cv_{config.selection.metric}_std" in info["metrics"]
        # Its own number, not the standing-val score relabelled.
        assert best["value"] != info["metrics"]["val_f1_macro"]

    @needs_trainer("lightgbm")
    def test_two_families_rank_against_each_other_in_one_output_dir(
        self, tmp_path, processed_file, caplog
    ):
        """The whole point: a pooled family and a standing-val one, one best."""
        import logging
        import time

        outputs = str(tmp_path / "outputs" / "comparison")
        cv_values = {}
        with caplog.at_level(logging.WARNING):
            for trainer in (RANDOM_FOREST_TRAINER, LIGHTGBM_TRAINER):
                config = make_training_config(
                    tmp_path,
                    processed_file,
                    trainer,
                    output_dir=outputs,
                    selection={"basis": "cv"},
                    diagnostics={"shap": {"enabled": False}},
                )
                run_dir = TrainingPipeline(config).run()
                metrics = load_metadata(run_dir)["training_info"]["metrics"]
                cv_values[trainer["kind"]] = metrics["cv_f1_macro"]
                # Run timestamps are second-granular and make_run_dir refuses
                # a collision, so the second run has to start a second later.
                time.sleep(1.1)

        # Same metric key, so the pointer ranks instead of refusing.
        assert "best.json left unchanged" not in caplog.text
        best = get_best_info(outputs)
        assert best["metric"] == "cv_f1_macro"
        assert best["value"] == max(cv_values.values())

    def test_a_pooled_family_is_unaffected_by_the_knob(self, tmp_path, processed_file):
        """A pooled run is already on the CV basis; ``cv`` changes nothing."""
        runs = {}
        for basis in ("auto", "cv"):
            config = make_training_config(
                tmp_path,
                processed_file,
                RANDOM_FOREST_TRAINER,
                output_dir=str(tmp_path / "outputs" / basis),
                selection={"basis": basis},
            )
            info = load_metadata(TrainingPipeline(config).run())["training_info"]
            runs[basis] = (info["selection_basis"], info["metrics"])

        assert runs["auto"][0] == runs["cv"][0] == "cv"
        assert runs["auto"][1] == runs["cv"][1]


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

    def test_a_seeded_search_replays(self, tmp_path, processed_file):
        """Same seed, same spec, same winners - or a tuned run is anecdote.

        Separate output dirs because the run timestamp is second-granular
        and ``make_run_dir`` refuses a collision.
        """
        pytest.importorskip("optuna", reason="needs the 'tune' extra")
        trainer = {**LOGREG_TRAINER, "tune": {"enabled": True, "n_trials": 2, "cv": 2}}
        winners = []
        for name in ("first", "second"):
            config = make_training_config(
                tmp_path,
                processed_file,
                trainer,
                output_dir=str(tmp_path / "outputs" / name),
            )
            run_dir = TrainingPipeline(config).run()
            winners.append(load_metadata(run_dir)["hyperparameters"]["best_params"])

        assert winners[0] == winners[1]

    def test_a_disabled_space_entry_is_left_to_the_config(self, tmp_path, processed_file):
        """``tune.space: {max_depth: false}`` takes one knob out of the search.

        The end-to-end half of the search-space contract: what the config
        pinned must survive the run and never appear among the winners.
        """
        pytest.importorskip("optuna", reason="needs the 'tune' extra")
        trainer = {
            **RANDOM_FOREST_TRAINER,
            "tune": {
                "enabled": True,
                "n_trials": 2,
                "cv": 2,
                "space": {"max_depth": False},
            },
        }
        config = make_training_config(tmp_path, processed_file, trainer)
        run_dir = TrainingPipeline(config).run()

        spec = load_metadata(run_dir)["hyperparameters"]
        assert spec["best_params"] and "max_depth" not in spec["best_params"]
        assert spec["params"]["max_depth"] == RANDOM_FOREST_TRAINER["params"]["max_depth"]
