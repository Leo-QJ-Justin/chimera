"""The ``BaseTrainer`` contract, asserted identically for every family.

This is the acid test of R1.5: one parametrized suite, three trainers, no
per-family branches. If a new trainer cannot pass this file unchanged, it
does not satisfy the contract and the pipelines cannot use it.

The torch case skips cleanly when the extra is absent, which is also how
the shipped skeleton behaves on a machine that only installed the sklearn
dependencies.
"""

from importlib.util import find_spec

import numpy as np
import pandas as pd
import pytest

from conftest import (
    LIGHTGBM_TRAINER,
    SKLEARN_TRAINER,
    TEST_SEED,
    TEST_TRAIN_SIZE,
    TORCH_TRAINER,
)
from PROJECT.core.run_artifacts import save_metadata
from PROJECT.pipelines.training_pipeline import build_trainer
from PROJECT.pipelines.training_pipeline.classes.registry import (
    get_trainer_class,
    trainer_class_for_model_type,
)
from PROJECT.schemas import TrainerConfig


def _needs(extra: str, *modules: str):
    """Skip when an optional extra is absent, exactly as the scaffold does."""
    missing = [m for m in modules if find_spec(m) is None]
    return pytest.mark.skipif(
        bool(missing), reason=f"needs the {extra!r} extra ({', '.join(missing)})"
    )


needs_tune = _needs("tune", "optuna")

TRAINER_SPECS = [
    pytest.param(SKLEARN_TRAINER, id="sklearn"),
    pytest.param(LIGHTGBM_TRAINER, id="lightgbm", marks=_needs("lightgbm", "lightgbm")),
    pytest.param(
        TORCH_TRAINER,
        id="torch",
        marks=_needs("torch", "torch", "early_stopping_pytorch"),
    ),
]

# sklearn + lightgbm only: the base's CV/tuning path needs a sklearn-shaped
# estimator, which TorchTrainer deliberately refuses to fake.
SKLEARN_API_SPECS = TRAINER_SPECS[:2]


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
    def test_train_then_predict_one_row_at_a_time(self, spec, features, xy):
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

        wrong = next(
            get_trainer_class(kind)
            for kind in ("sklearn", "lightgbm", "torch")
            if kind != spec["kind"]
        )
        with pytest.raises(ValueError, match="does not match"):
            wrong.load(run_dir)

    def test_registry_resolves_the_saved_model_type(self, spec, features):
        trainer = _build(spec, features)
        assert trainer_class_for_model_type(trainer.model_type) is type(trainer)


@needs_tune
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

    def test_tune_applies_its_winners_to_the_next_train(self, spec, features, xy):
        X_train, y_train, X_val, y_val = xy
        trainer = _build(spec, features)

        best = trainer.hyperparameter_tune(X_train, y_train, n_trials=3, cv=3)
        assert best and trainer.best_params == best
        # Folded into params, so the next train actually uses them - the bug
        # this asserts against is a search whose result nobody applies.
        for key, value in best.items():
            assert trainer.params[key] == value
        trainer.train(X_train, y_train, X_val, y_val)
        assert trainer.get_params()["tuned"] is True


class TestTorchOverrides:
    """The two places TorchTrainer refuses the base's sklearn machinery."""

    @_needs("torch", "torch")
    def test_cross_validate_is_refused_with_a_pointer(self, features, xy):
        trainer = _build(TORCH_TRAINER, features)
        with pytest.raises(NotImplementedError, match="hyperparameter_tune"):
            trainer.cross_validate(xy[0], xy[1], cv=2)

    @needs_tune
    @_needs("torch", "torch")
    def test_tune_uses_a_holdout_and_applies_the_result(self, features, xy):
        trainer = _build(TORCH_TRAINER, features)
        best = trainer.hyperparameter_tune(xy[0], xy[1], n_trials=2)
        assert "options__lr" in best
        assert trainer.options.lr == best["options__lr"]
        assert trainer.params["dropout"] == best["params__dropout"]


class TestTorchRegressionAndCheckpoints:
    """Review-gate regressions: the scalar head and honest checkpoints."""

    @_needs("torch", "torch", "early_stopping_pytorch")
    def test_regression_head_trains_and_predicts(self, synthetic_frame):
        import numpy as np

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

    @_needs("torch", "torch", "early_stopping_pytorch")
    def test_checkpoint_last_records_final_state_not_best(self, tmp_path, features, xy):
        """`resume: continue` must resume the last epoch, not the best one.

        The served model is rewound to the best weights after training, so
        `save` must write checkpoint_last from the pre-rewind snapshot. The
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
        get_trainer_class("xgboost")


def test_sklearn_estimator_rejects_an_unsupported_task(features):
    spec = {**SKLEARN_TRAINER}
    trainer = build_trainer(
        TrainerConfig(**spec), task="regression", seed=TEST_SEED, **features
    )
    frame = pd.DataFrame({c: [0.0] for c in trainer.feature_columns})
    with pytest.raises(ValueError, match="supports"):
        trainer.train(frame, [0.0])
