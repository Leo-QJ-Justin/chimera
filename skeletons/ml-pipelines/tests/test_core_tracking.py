import importlib.util

import pytest

from PROJECT.core import tracking as tr


def test_disabled_tracker_is_noop_but_sidecar_writes(tmp_path):
    tracker = tr.init_tracking(enabled=False, run_dir=tmp_path)
    assert not tracker.live
    tracker.log_params({"lr": 0.001})
    tracker.log_metrics({"loss": 1.0}, step=1)
    tracker.log_metrics({"loss": 0.5}, step=2)
    tracker.log_artifact(tmp_path)  # no-op, must not raise
    tracker.end()
    df = tr.load_sidecar_metrics(tmp_path)
    assert len(df) == 2
    assert df.loc[df.step == 2, "value"].item() == 0.5


def test_no_run_dir_means_no_sidecar(tmp_path):
    tracker = tr.init_tracking(enabled=False)
    tracker.log_metrics({"loss": 1.0})
    tracker.end()
    with pytest.raises(FileNotFoundError):
        tr.load_sidecar_metrics(tmp_path)


def test_missing_mlflow_degrades_not_raises(tmp_path, monkeypatch):
    # Force the import inside the factory to fail even if mlflow exists.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("mlflow"):
            raise ImportError("simulated absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    tracker = tr.init_tracking(enabled=True, run_dir=tmp_path)
    assert not tracker.live
    tracker.log_metrics({"loss": 1.0}, step=1)
    tracker.end()


@pytest.mark.skipif(
    importlib.util.find_spec("mlflow") is None, reason="mlflow not installed"
)
def test_live_tracker_logs_to_local_store(tmp_path):
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    tracker = tr.init_tracking(
        enabled=True,
        tracking_uri=uri,
        experiment_name="skeleton-test",
        run_name="t1",
        run_dir=tmp_path / "run",
    )
    assert tracker.live
    tracker.log_params({"lr": 0.001, "n": 2})
    tracker.log_metrics({"loss": 0.9}, step=1)
    tracker.set_tags({"tier": "test"})
    tracker.end()
    from mlflow.tracking import MlflowClient

    client = MlflowClient(tracking_uri=uri)
    run = client.get_run(tracker.run_id)
    assert run.data.params["lr"] == "0.001"
    assert run.data.metrics["loss"] == 0.9
