"""The ``BaseTrainer`` contract, asserted identically for every family.

This is the acid test of R1.5: one parametrized suite, five trainers, no
per-family branches. If a new trainer cannot pass this file unchanged, it
does not satisfy the contract and the pipelines cannot use it.

Optional-extra families skip cleanly, which is also how the shipped
skeleton behaves on a machine that installed only the sklearn dependencies.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import PROJECT
from conftest import (
    ALL_TRAINERS,
    LIGHTGBM_TRAINER,
    LOGREG_TRAINER,
    RANDOM_FOREST_TRAINER,
    TEST_SEED,
    TEST_TRAIN_SIZE,
    TORCH_TRAINER,
    XGBOOST_TRAINER,
    needs,
    needs_trainer,
    trainer_params,
)
from PROJECT.core.run_artifacts import save_metadata
from PROJECT.pipelines.training_pipeline import build_trainer, get_trainer_class
from PROJECT.pipelines.training_pipeline.classes import TRAINERS
from PROJECT.schemas import TrainerConfig

needs_tune = needs("optuna", reason="the 'tune' extra")

TRAINER_SPECS = trainer_params()

# Everything except torch: the base's CV/tuning path needs a sklearn-shaped
# estimator, which TorchTrainer deliberately refuses to fake.
SKLEARN_API_SPECS = [p for p in TRAINER_SPECS if p.id != "torch"]


def _build(spec: dict, features: dict, **overrides):
    return build_trainer(
        TrainerConfig(**spec),
        task="classification",
        seed=TEST_SEED,
        cv_mode="stratified",
        **features,
        **overrides,
    )


@pytest.mark.parametrize("spec", TRAINER_SPECS)
class TestContract:
    def test_train_then_predict(self, spec, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features).train(X_train, y_train, X_val, y_val)

        predictions = trainer.predict(X_val)
        assert len(predictions) == len(X_val)
        assert set(np.unique(predictions)) <= set(np.unique(y_train))

    def test_predict_before_train_raises(self, spec, features, xy):
        trainer = _build(spec, features)
        with pytest.raises(RuntimeError, match="not fitted"):
            trainer.predict(xy[0])

    def test_evaluate_returns_the_project_metrics(self, spec, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features).train(X_train, y_train, X_val, y_val)

        metrics = trainer.evaluate(X_val, y_val)
        assert set(metrics) == {"accuracy", "f1_macro"}
        assert all(0.0 <= v <= 1.0 for v in metrics.values())

    def test_evaluate_accepts_named_and_callable_metrics(self, spec, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features).train(X_train, y_train, X_val, y_val)

        def hit_rate(y_true, y_pred):
            return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))

        metrics = trainer.evaluate(
            X_val, y_val, metrics=["balanced_accuracy_score", hit_rate]
        )
        assert set(metrics) == {"balanced_accuracy_score", "hit_rate"}

    def test_column_order_does_not_change_predictions(self, spec, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features).train(X_train, y_train, X_val, y_val)

        shuffled = X_val[list(reversed(X_val.columns))]
        assert trainer.predict(shuffled).tolist() == trainer.predict(X_val).tolist()

    def test_missing_feature_column_raises(self, spec, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features).train(X_train, y_train, X_val, y_val)
        with pytest.raises(ValueError, match="missing 1 feature column"):
            trainer.predict(X_val.drop(columns=[X_val.columns[0]]))

    def test_save_load_roundtrip_predicts_identically(self, spec, features, xy, tmp_path):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features).train(X_train, y_train, X_val, y_val)

        run_dir = tmp_path / spec["kind"]
        run_dir.mkdir()
        files = trainer.save(run_dir)
        # The files map names real filenames, never paths.
        assert files and all("/" not in name for name in files.values())
        _write_metadata(run_dir, trainer, files)

        reloaded = type(trainer).load(run_dir)
        assert reloaded.model_type == trainer.model_type
        assert reloaded.feature_columns == trainer.feature_columns
        assert reloaded.predict(X_val).tolist() == trainer.predict(X_val).tolist()

    def test_load_refuses_another_trainers_run(self, spec, features, xy, tmp_path):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features).train(X_train, y_train, X_val, y_val)
        run_dir = tmp_path / "mismatch"
        run_dir.mkdir()
        _write_metadata(run_dir, trainer, trainer.save(run_dir))

        # A family with no optional extra, so the class guard is what fails.
        other = "random_forest" if spec["kind"] == "logreg" else "logreg"
        with pytest.raises(ValueError, match="does not match"):
            get_trainer_class(other).load(run_dir)

    def test_registry_resolves_the_saved_model_type(self, spec, features):
        trainer = _build(spec, features)
        # model_type IS the family key: one string names class, config and run.
        assert trainer.model_type == spec["kind"]
        assert get_trainer_class(trainer.model_type) is type(trainer)


@pytest.mark.parametrize("spec", SKLEARN_API_SPECS)
class TestCrossValidationAndTuning:
    def test_cross_validate_reports_mean_and_std(self, spec, features, xy):
        X_train, y_train, _, _ = xy
        trainer = _build(spec, features)

        results = trainer.cross_validate(X_train, y_train, cv=3)
        assert set(results) == {"accuracy", "f1_macro"}
        assert all({"mean", "std"} == set(v) for v in results.values())

    def test_cross_validate_does_not_fit_the_trainer(self, spec, features, xy):
        # A fresh model per fold is the whole point; the trainer's own model
        # must be untouched afterwards.
        X_train, y_train, _, _ = xy
        trainer = _build(spec, features)
        trainer.cross_validate(X_train, y_train, cv=3)
        assert not trainer.fitted

    @needs_tune
    def test_tune_applies_its_winners_to_the_next_train(self, spec, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features)

        best = trainer.hyperparameter_tune(X_train, y_train, n_trials=2, cv=3)
        assert best and trainer.best_params == best
        # Folded into params, so the next train actually uses them - the bug
        # this asserts against is a search whose result nobody applies.
        for key, value in best.items():
            assert trainer.params[key] == value
        trainer.train(X_train, y_train, X_val, y_val)
        assert trainer.get_params()["tuned"] is True


class TestPerFamilySpaces:
    """Each family tunes over its own space, not a shared one."""

    @needs_tune
    def test_logreg_space_carries_its_derived_penalty(self, features, xy):
        """A value derived from a suggestion must survive into params.

        ``study.best_params`` holds only what Optuna suggested; ``penalty``
        is derived from the sampled solver, so it reaches ``params`` solely
        because the tuner records the *resolved* dict per trial.
        """
        trainer = _build(LOGREG_TRAINER, features)
        best = trainer.hyperparameter_tune(xy[0], xy[1], n_trials=4, cv=2)
        assert {"C", "solver", "class_weight"} <= set(best)
        if best["solver"] == "saga":
            assert best["penalty"] == "elasticnet"
            assert 0.0 <= best["l1_ratio"] <= 1.0

    @needs_tune
    @needs_trainer("xgboost")
    def test_xgboost_space_is_its_own(self, features, xy):
        trainer = _build(XGBOOST_TRAINER, features)
        best = trainer.hyperparameter_tune(xy[0], xy[1], n_trials=2, cv=2)
        assert set(best) == {
            "learning_rate",
            "max_depth",
            "subsample",
            "colsample_bytree",
            "min_child_weight",
            "n_estimators",
        }

    def test_random_forest_space_differs_from_logregs(self, features):
        """Two sklearn families, two spaces - no shared estimator table."""
        forest = _build(RANDOM_FOREST_TRAINER, features)
        linear = _build(LOGREG_TRAINER, features)
        trial = _StubTrial()
        assert "max_features" in forest._get_param_space(trial)
        assert "max_features" not in linear._get_param_space(trial)


class TestBoosterEarlyStopping:
    """Both boosters must actually stop on the validation split."""

    @needs_trainer("xgboost")
    def test_xgboost_early_stopping_engages(self, features, xy):
        X_train, y_train, X_val, y_val = xy
        # Far more rounds than this tiny frame can keep improving on, so
        # stopping has to fire before the last one.
        trainer = _build(
            {**XGBOOST_TRAINER, "params": {"n_estimators": 400, "max_depth": 3}}, features
        )
        trainer.train(X_train, y_train, X_val, y_val)

        assert trainer.best_iteration is not None
        assert trainer.best_iteration < 399
        assert trainer.training_summary()["early_stopping_rounds"] == 5

    @needs_trainer("xgboost")
    def test_xgboost_without_a_validation_split_trains_full(self, features, xy):
        # early_stopping_rounds with no eval_set raises in xgboost, so the
        # trainer must not attach it. This is that guard.
        trainer = _build(XGBOOST_TRAINER, features)
        trainer.train(xy[0], xy[1])
        assert trainer.best_iteration is None

    @needs_trainer("lightgbm")
    def test_lightgbm_early_stopping_engages(self, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(
            {**LIGHTGBM_TRAINER, "params": {"n_estimators": 400, "verbose": -1}}, features
        )
        trainer.train(X_train, y_train, X_val, y_val)
        assert trainer.best_iteration is not None
        assert trainer.best_iteration < 400


class TestBoosterHistory:
    """A booster's eval curve must reach ``history`` in the shared shape.

    The orchestrator replays ``history`` into the tracker step-wise using
    the ``epoch`` key - so a booster that records its curve gets per-round
    MLflow metrics and a training-curve figure with no trainer-side
    tracking code, exactly as the torch trainer does.
    """

    @pytest.mark.parametrize(
        "spec",
        [
            pytest.param(
                LIGHTGBM_TRAINER, id="lightgbm", marks=needs_trainer("lightgbm")
            ),
            pytest.param(XGBOOST_TRAINER, id="xgboost", marks=needs_trainer("xgboost")),
        ],
    )
    def test_validation_curve_is_captured_per_iteration(self, spec, features, xy):
        trainer = _build(spec, features).train(*xy)

        assert trainer.history, "the booster recorded no eval curve"
        first = trainer.history[0]
        assert first["epoch"] == 0
        assert [r["epoch"] for r in trainer.history] == list(range(len(trainer.history)))
        val_keys = [k for k in first if k.startswith("val_")]
        assert val_keys, f"no val_* metric in {sorted(first)}"
        assert all(isinstance(first[k], float) for k in val_keys)

    @pytest.mark.parametrize(
        "spec",
        [
            pytest.param(
                LIGHTGBM_TRAINER, id="lightgbm", marks=needs_trainer("lightgbm")
            ),
            pytest.param(XGBOOST_TRAINER, id="xgboost", marks=needs_trainer("xgboost")),
        ],
    )
    def test_no_validation_split_records_no_history(self, spec, features, xy):
        # Nothing to record against, and an empty history is the honest
        # answer - the curve helpers treat it as "no curves", not an error.
        trainer = _build(spec, features).train(xy[0], xy[1])
        assert trainer.history == []


class TestBoosterHistoryShape:
    """The flattener itself, on the nested shape both boosters produce."""

    def test_dataset_names_become_split_prefixes(self):
        from PROJECT.pipelines.training_pipeline.modules.history import booster_history

        history = booster_history(
            {
                "training": {"logloss": [0.7, 0.6]},
                "validation_0": {"logloss": [0.8, 0.75]},
            }
        )
        assert history == [
            {"epoch": 0, "train_logloss": 0.7, "val_logloss": 0.8},
            {"epoch": 1, "train_logloss": 0.6, "val_logloss": 0.75},
        ]

    def test_ragged_series_are_truncated_not_padded(self):
        """A curve cut short by early stopping must not leave partial rows."""
        from PROJECT.pipelines.training_pipeline.modules.history import booster_history

        history = booster_history({"valid_0": {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0]}})
        assert len(history) == 2
        assert all({"epoch", "val_a", "val_b"} == set(r) for r in history)

    def test_no_eval_record_is_an_empty_history(self):
        from PROJECT.pipelines.training_pipeline.modules.history import booster_history

        assert booster_history({}) == []
        assert booster_history(None) == []


class TestTorchOverrides:
    """The two places TorchTrainer refuses the base's sklearn machinery."""

    @needs_trainer("torch")
    def test_cross_validate_is_refused_with_a_pointer(self, features, xy):
        trainer = _build(TORCH_TRAINER, features)
        with pytest.raises(NotImplementedError, match="hyperparameter_tune"):
            trainer.cross_validate(xy[0], xy[1], cv=2)

    @needs_tune
    @needs_trainer("torch")
    def test_tune_uses_a_holdout_and_applies_the_result(self, features, xy):
        trainer = _build(TORCH_TRAINER, features)
        best = trainer.hyperparameter_tune(xy[0], xy[1], n_trials=2)
        assert trainer.options.lr == best["options__lr"]
        assert trainer.params["dropout"] == best["params__dropout"]
        # hidden_sizes is derived from a width and a depth, so it exists only
        # because the resolved suggestion is recorded per trial.
        assert trainer.params["hidden_sizes"] == best["params__hidden_sizes"]


class TestTorchRegressionAndCheckpoints:
    """Review-gate regressions: the scalar head and honest checkpoints."""

    @needs_trainer("torch")
    def test_regression_head_trains_and_predicts(self, synthetic_frame):
        trainer = build_trainer(
            TrainerConfig(**TORCH_TRAINER),
            task="regression",
            seed=TEST_SEED,
            cv_mode="stratified",
            numeric_features=["num_b"],
            categorical_features=["cat_a"],
        )
        X = synthetic_frame[["num_b", "cat_a"]]
        y = synthetic_frame["num_a"]  # continuous target
        cut = int(len(X) * TEST_TRAIN_SIZE)
        trainer.train(X.iloc[:cut], y.iloc[:cut], X.iloc[cut:], y.iloc[cut:])
        assert trainer.n_outputs == 1
        preds = trainer.predict(X.iloc[cut:])
        assert preds.shape == (len(X) - cut,)
        assert np.isfinite(preds).all()

    @needs_trainer("torch")
    def test_checkpoint_last_records_final_state_not_best(self, tmp_path, features, xy):
        """``resume: continue`` must resume the last epoch, not the best one.

        The served model is rewound to the best weights after training, so
        ``save`` must write checkpoint_last from the pre-rewind snapshot. The
        snapshot is perturbed here to make the two distinguishable even when
        the best epoch happened to be the final one.
        """
        import torch

        trainer = _build(TORCH_TRAINER, features)
        trainer.train(*xy)
        if trainer._best_state is None:
            pytest.skip("no best checkpoint written this run")
        bumped = {k: v + 1.0 for k, v in trainer._last_state.items()}
        trainer._last_state = bumped
        files = trainer.save(tmp_path)
        last = torch.load(tmp_path / files["checkpoint_last"], weights_only=False)
        assert all(torch.equal(last["model_state_dict"][k], v) for k, v in bumped.items())
        best = torch.load(tmp_path / files["checkpoint_best"], weights_only=False)
        assert any(not torch.equal(best[k], v) for k, v in bumped.items())


class _StubTrial:
    """A minimal Optuna trial stand-in: takes the low end of every range."""

    def suggest_int(self, name, low, *args, **kwargs):
        return low

    def suggest_float(self, name, low, *args, **kwargs):
        return low

    def suggest_categorical(self, name, choices):
        return choices[0]


def _write_metadata(run_dir, trainer, files: dict) -> None:
    """The metadata a training run would have written, minus the run detail."""
    save_metadata(
        run_dir=run_dir,
        model_type=trainer.model_type,
        timestamp="20260101_000000",
        feature_columns=trainer.feature_columns,
        target_columns=["target"],
        hyperparameters=trainer.spec(),
        training_info={},
        files=files,
    )


def test_unknown_trainer_kind_lists_what_exists():
    with pytest.raises(KeyError, match="registered"):
        get_trainer_class("catboost")


def test_every_registered_kind_has_a_config_group_file():
    """``trainer=<kind>`` must always be the way to switch families."""
    group = Path(PROJECT.__file__).parent / "pipelines/training_pipeline/configs/trainer"
    declared = {
        line.split(":", 1)[1].strip()
        for path in group.glob("*.yaml")
        for line in path.read_text().splitlines()
        if line.startswith("kind:")
    }
    assert declared == set(TRAINERS)


def test_the_contract_suite_covers_every_registered_family():
    """A new family must not be able to skip this file quietly."""
    assert set(ALL_TRAINERS) == set(TRAINERS)


def test_logreg_rejects_a_regression_task(features):
    trainer = build_trainer(
        TrainerConfig(**LOGREG_TRAINER), task="regression", seed=TEST_SEED, **features
    )
    frame = pd.DataFrame({c: [0.0] for c in trainer.feature_columns})
    with pytest.raises(ValueError, match="classifier"):
        trainer.train(frame, [0.0])
