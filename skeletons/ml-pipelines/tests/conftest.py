"""Shared fixtures.

Test constants come from schema defaults, never from the YAML in
``configs/``: those files are meant to be edited per project, so a test that
read them would fail as soon as a knob was tuned.

Every config fixture sets ``mlflow.enabled=false`` - declaratively, the
same switch production uses, not by monkeypatching - so the suite is
hermetic even though the shipped base config turns tracking on.
"""

from importlib.util import find_spec

import numpy as np
import pandas as pd
import pytest

from PROJECT.pipelines.training_pipeline import TrainingPipeline
from PROJECT.schemas import (
    DataPipelineConfig,
    EvaluationConfig,
    InferenceConfig,
    TrainingConfig,
    TrainingSplitConfig,
)

_data_defaults = DataPipelineConfig()
_split_defaults = TrainingSplitConfig()

TEST_SEED: int = _data_defaults.seed
TEST_KEY_COLS: list[str] = list(_data_defaults.key_cols)
TEST_TARGET: str = _data_defaults.target
TEST_DATE_COL: str = _data_defaults.date_col
TEST_TRAIN_SIZE: float = _split_defaults.train_size

N_ROWS = 240

# Tiny by design: these tests assert the contract (which artifacts exist,
# that a reload predicts), not model quality. One entry per shipped family,
# keyed by `kind` exactly as the config group files are.
LOGREG_TRAINER = {"kind": "logreg", "params": {"max_iter": 200}}
RANDOM_FOREST_TRAINER = {
    "kind": "random_forest",
    "params": {"n_estimators": 20, "max_depth": 4},
}
LIGHTGBM_TRAINER = {
    "kind": "lightgbm",
    "params": {"n_estimators": 40, "verbose": -1},
    "lightgbm": {"early_stopping_rounds": 10},
}
XGBOOST_TRAINER = {
    "kind": "xgboost",
    "params": {"n_estimators": 40, "max_depth": 3},
    "xgboost": {"early_stopping_rounds": 5},
}
TORCH_TRAINER = {
    "kind": "torch",
    "params": {"hidden_sizes": [16]},
    "torch": {"epochs": 3, "batch_size": 32, "patience": 5},
}

# Every shipped family, in registry order. Tests parametrize over this so a
# new family is one entry here plus its class - never a new test file.
ALL_TRAINERS = {
    "logreg": LOGREG_TRAINER,
    "random_forest": RANDOM_FOREST_TRAINER,
    "lightgbm": LIGHTGBM_TRAINER,
    "xgboost": XGBOOST_TRAINER,
    "torch": TORCH_TRAINER,
}

# Optional extras a family needs, for skipif marks. Empty -> always runnable.
TRAINER_EXTRAS = {
    "logreg": (),
    "random_forest": (),
    "lightgbm": ("lightgbm",),
    "xgboost": ("xgboost",),
    "torch": ("torch", "early_stopping_pytorch"),
}


def needs(*modules: str, reason: str = ""):
    """Skip when an optional extra is absent, exactly as the scaffold does.

    Actually imports rather than probing ``find_spec``: an installed-but-
    unimportable extra (shap under a numpy that numba does not support yet)
    must skip the same way an absent one does, because that is what the
    scaffold's guarded imports do at run time.
    """
    missing = [m for m in modules if not _importable(m)]
    return pytest.mark.skipif(
        bool(missing), reason=f"needs {reason or 'the extra'} ({', '.join(missing)})"
    )


def _importable(module: str) -> bool:
    if find_spec(module) is None:
        return False
    try:
        __import__(module)
    except ImportError:
        return False
    return True


def needs_trainer(kind: str):
    """Skip when the family's optional extra is absent."""
    return needs(*TRAINER_EXTRAS[kind], reason=f"the {kind!r} extra")


def trainer_params():
    """One ``pytest.param`` per shipped family, each skipping cleanly.

    Parametrizing over this keeps the contract suite complete: a new family
    is one entry in ``ALL_TRAINERS`` and no new test.
    """
    return [
        pytest.param(spec, id=kind, marks=needs_trainer(kind))
        for kind, spec in ALL_TRAINERS.items()
    ]


@pytest.fixture
def synthetic_frame() -> pd.DataFrame:
    """A tiny, deterministic tabular frame with keys, mixed dtypes, label."""
    rng = np.random.default_rng(TEST_SEED)
    dates = pd.date_range("2024-01-01", periods=N_ROWS, freq="D")
    numeric_signal = rng.normal(size=N_ROWS)
    return pd.DataFrame(
        {
            "entity_id": [f"e{i % 12:02d}" for i in range(N_ROWS)],
            "date": dates,
            "num_a": numeric_signal,
            "num_b": rng.normal(size=N_ROWS),
            "cat_a": rng.choice(["red", "green", "blue"], size=N_ROWS),
            # Learnable but not separable, so metrics are non-degenerate.
            "target": (numeric_signal + rng.normal(scale=0.5, size=N_ROWS) > 0).astype(
                int
            ),
        }
    )


@pytest.fixture
def processed_file(tmp_path, synthetic_frame) -> str:
    """A model-input table on disk, as the data pipeline leaves it."""
    path = tmp_path / "model_input.parquet"
    synthetic_frame.to_parquet(path, index=False)
    return str(path)


@pytest.fixture
def features(synthetic_frame) -> dict[str, list[str]]:
    """The feature split a trainer is constructed with."""
    return {
        "numeric_features": ["num_a", "num_b"],
        "categorical_features": ["cat_a"],
    }


@pytest.fixture
def xy(synthetic_frame, features):
    """``(X_train, y_train, X_val, y_val)`` for direct trainer tests."""
    cut = int(len(synthetic_frame) * TEST_TRAIN_SIZE)
    columns = [*features["numeric_features"], *features["categorical_features"]]
    train, val = synthetic_frame.iloc[:cut], synthetic_frame.iloc[cut:]
    return train[columns], train[TEST_TARGET], val[columns], val[TEST_TARGET]


def make_training_config(tmp_path, processed_file, trainer: dict, **overrides):
    """Training config pointed at tmp_path, tracking off."""
    base = {
        "processed_path": processed_file,
        "output_dir": str(tmp_path / "outputs" / "training"),
        "target": TEST_TARGET,
        "key_cols": TEST_KEY_COLS,
        "seed": TEST_SEED,
        "trainer": trainer,
        "split": {"mode": "stratified", "seed": TEST_SEED},
        "mlflow": {"enabled": False},
    }
    return TrainingConfig(**{**base, **overrides})


@pytest.fixture
def training_config(tmp_path, processed_file) -> TrainingConfig:
    """The default (logreg) training config for the pipeline tests."""
    return make_training_config(tmp_path, processed_file, LOGREG_TRAINER)


@pytest.fixture
def trained_run(training_config):
    """An executed training run; yields ``(run_dir, config)``."""
    return TrainingPipeline(training_config).run(), training_config


@pytest.fixture
def inference_config_factory(tmp_path):
    """Builds an inference config against a given training run."""

    def build(training_config, **overrides) -> InferenceConfig:
        base = {
            "model": {"use": "best", "runs_dir": training_config.output_dir},
            "input_path": training_config.processed_path,
            "output_path": str(tmp_path / "predictions.parquet"),
            "key_cols": TEST_KEY_COLS,
            "mlflow": {"enabled": False},
        }
        return InferenceConfig(**{**base, **overrides})

    return build


@pytest.fixture
def evaluation_config_factory(tmp_path):
    """Builds an evaluation config against a predictions file."""

    def build(predictions_path, training_config, **overrides) -> EvaluationConfig:
        base = {
            "predictions_path": str(predictions_path),
            "processed_path": training_config.processed_path,
            "output_dir": str(tmp_path / "outputs" / "evaluation"),
            "target": TEST_TARGET,
            "key_cols": TEST_KEY_COLS,
            "runs_dir": training_config.output_dir,
            "mlflow": {"enabled": False},
        }
        return EvaluationConfig(**{**base, **overrides})

    return build
