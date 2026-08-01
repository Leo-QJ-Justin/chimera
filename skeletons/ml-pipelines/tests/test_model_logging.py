"""Curated MLflow model logging: the artifact lands, and it loads back.

The scaffold logs models through ``mlflow.<flavor>.save_model`` plus
``tracker.log_artifacts``, never the fluent ``log_model`` API - the core
Tracker drives ``MlflowClient`` with an explicit ``run_id`` so that no
pipeline depends on fluent global state. These tests assert the outcome of
that choice: a ``model/`` artifact in the run's own artifact store which
``mlflow.<flavor>.load_model`` can read.

The tracking backend is a sqlite file and the artifact root is ``tmp_path``,
so nothing here touches the repo or a shared store.
"""

import importlib

import pytest

from conftest import (
    ALL_TRAINERS,
    LOGREG_TRAINER,
    TEST_SEED,
    make_training_config,
    needs,
    needs_trainer,
)
from PROJECT.core.tracking import init_tracking
from PROJECT.pipelines.training_pipeline import TrainingPipeline, build_trainer
from PROJECT.schemas import TrainerConfig

pytestmark = needs("mlflow", reason="mlflow")

# The flavor each family logs itself in. Kept beside the trainers rather than
# inferred: "which flavor" is a per-family decision, and this is the assertion
# that it was made deliberately.
FLAVORS = {
    "logreg": "sklearn",
    "random_forest": "sklearn",
    "lightgbm": "lightgbm",
    "xgboost": "xgboost",
    "torch": "pytorch",
}


@pytest.fixture
def backend(tmp_path, monkeypatch):
    """A private sqlite tracking backend with a local artifact root.

    The experiment is created up front with an explicit ``artifact_location``
    so its artifacts land under tmp_path. The chdir contains the separate
    ``mlruns/`` that MLflow creates for its own Default experiment, which
    would otherwise appear beside whatever directory pytest was run from.
    """
    from mlflow.tracking import MlflowClient

    monkeypatch.chdir(tmp_path)
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    client = MlflowClient(tracking_uri=uri)
    client.create_experiment("test", artifact_location=str(tmp_path / "artifacts"))
    return uri, client


@pytest.fixture
def mlflow_config(backend):
    """The ``mlflow`` config section pointed at that backend, tracking ON."""
    uri, _ = backend
    return {"enabled": True, "tracking_uri": uri, "experiment_name": "test"}


@pytest.fixture
def tracking(backend, tmp_path):
    """A live Tracker on the private backend."""
    uri, client = backend
    tracker = init_tracking(
        enabled=True,
        tracking_uri=uri,
        experiment_name="test",
        run_name="model-logging",
        run_dir=tmp_path / "run",
    )
    assert tracker.live, "the fixture must produce a live tracker, not a no-op"
    yield tracker, client
    tracker.end()


def _artifact_dir(client, run_id: str) -> str:
    return f"{client.get_run(run_id).info.artifact_uri}/model"


@pytest.mark.parametrize(
    "kind",
    [pytest.param(k, id=k, marks=needs_trainer(k)) for k in ALL_TRAINERS],
)
def test_each_family_logs_a_loadable_model_in_its_flavor(kind, tracking, features, xy):
    tracker, client = tracking
    X_train, y_train, X_val, y_val = xy
    trainer = build_trainer(
        TrainerConfig(**ALL_TRAINERS[kind]),
        task="classification",
        seed=TEST_SEED,
        **features,
    ).train(X_train, y_train, X_val, y_val)

    trainer.log_model(tracker, X_val.head(5))

    # It landed in the run's artifact store, under model/.
    names = {f.path for f in client.list_artifacts(tracker.run_id, "model")}
    assert "model/MLmodel" in names

    # And it loads back through the flavor the family chose.
    flavor = importlib.import_module(f"mlflow.{FLAVORS[kind]}")
    loaded = flavor.load_model(_artifact_dir(client, tracker.run_id))
    assert loaded is not None


def test_the_training_pipeline_logs_the_model_after_the_fit(
    tmp_path, processed_file, backend, mlflow_config
):
    """The pipeline, not the caller, is what triggers logging."""
    _, client = backend
    config = make_training_config(
        tmp_path, processed_file, LOGREG_TRAINER, mlflow=mlflow_config
    )
    TrainingPipeline(config).run()

    run = _only_run(client)
    names = {f.path for f in client.list_artifacts(run.info.run_id, "model")}
    assert "model/MLmodel" in names


def test_logging_never_aborts_the_run(
    tmp_path, processed_file, backend, mlflow_config, monkeypatch
):
    """A flavor failure must cost the run nothing but a warning.

    Tracking is genuinely live here - with it off the pipeline never calls
    log_model at all, and the test would prove nothing.
    """
    from PROJECT.pipelines.training_pipeline.classes import logreg_trainer

    def explode(*args, **kwargs):
        raise RuntimeError("flavor exploded")

    monkeypatch.setattr(logreg_trainer, "log_flavor_model", explode)
    config = make_training_config(
        tmp_path, processed_file, LOGREG_TRAINER, mlflow=mlflow_config
    )
    run_dir = TrainingPipeline(config).run()

    # The run kept everything it wrote; only the model artifact is missing.
    assert (run_dir / "metadata.json").exists()
    _, client = backend
    run = _only_run(client)
    assert not client.list_artifacts(run.info.run_id, "model")


def test_diagnostic_plots_reach_the_runs_artifact_store(
    tmp_path, processed_file, backend, mlflow_config
):
    """Figures need no tracking call of their own to become artifacts.

    They are written into the run directory, and the pipeline uploads that
    directory wholesale - which is the whole reason ``core/plots.py`` takes
    a path and knows nothing about the tracker.
    """
    _, client = backend
    config = make_training_config(
        tmp_path,
        processed_file,
        LOGREG_TRAINER,
        mlflow=mlflow_config,
        diagnostics={"shap": {"enabled": False}},
    )
    TrainingPipeline(config).run()

    run = _only_run(client)
    names = {f.path for f in client.list_artifacts(run.info.run_id, "plots")}
    assert "plots/feature_importances.png" in names
    assert "plots/feature_importances.csv" in names


def _only_run(client):
    experiment = client.get_experiment_by_name("test")
    (run,) = client.search_runs([experiment.experiment_id])
    return run
