"""MLflow-optional experiment tracking with a structured local sidecar.

Contract (evidence-driven):

- **Never fail the pipeline.** Tracking errors log a warning and the run
  continues; local filesystem artifacts are always written regardless.
- **Optional by construction.** ``init_tracking`` checks ``enabled`` and
  the mlflow import *inside the factory* and returns a no-op tracker when
  either is off - call sites never branch.
- **Plain kwargs passthrough.** No signature filtering: a wrong kwarg
  raises in the wrapped call and is logged, instead of being silently
  dropped.
- **Structured metrics sidecar.** Every metric also lands in
  ``<run_dir>/metrics.jsonl`` so curves are recoverable without a
  tracking server and nobody ever parses prose logs.
"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_PARAM_CHUNK = 100
_METRIC_CHUNK = 1000


def init_tracking(
    enabled: bool,
    tracking_uri: str = "sqlite:///mlflow.db",
    experiment_name: str = "default",
    run_name: str | None = None,
    run_dir: str | Path | None = None,
    tags: dict | None = None,
) -> "Tracker":
    """Factory for a tracker; the enabled/import checks live here.

    Returns a live MLflow-backed tracker, or a no-op tracker (sidecar
    still active if ``run_dir`` given) when disabled or mlflow is absent.

    Note: the classic ``./mlruns`` file store is in maintenance mode on
    MLflow >= 3.x and raises at init unless ``MLFLOW_ALLOW_FILE_STORE`` is
    set; the sqlite default here works everywhere (UI:
    ``mlflow ui --backend-store-uri sqlite:///mlflow.db``).
    """
    sidecar = MetricsSidecar(run_dir) if run_dir else None
    if not enabled:
        return Tracker(None, None, sidecar)
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError:
        logger.warning("mlflow not installed; tracking disabled, sidecar only")
        return Tracker(None, None, sidecar)
    try:
        client = MlflowClient(tracking_uri=tracking_uri)
        experiment = client.get_experiment_by_name(experiment_name)
        if experiment is None:
            experiment_id = client.create_experiment(experiment_name)
        elif experiment.lifecycle_stage == "deleted":
            client.restore_experiment(experiment.experiment_id)
            experiment_id = experiment.experiment_id
        else:
            experiment_id = experiment.experiment_id
        run = client.create_run(
            experiment_id=experiment_id,
            run_name=run_name,
            tags=tags or {},
        )
        return Tracker(client, run.info.run_id, sidecar)
    except Exception as e:  # tracking must never abort the pipeline
        logger.warning("MLflow init failed (%s); continuing without tracking", e)
        return Tracker(None, None, sidecar)


class Tracker:
    """Uniform tracking surface; no-ops cleanly when not live."""

    def __init__(self, client, run_id: str | None, sidecar: "MetricsSidecar | None"):
        self._client = client
        self._run_id = run_id
        self._sidecar = sidecar

    @property
    def live(self) -> bool:
        return self._client is not None

    @property
    def run_id(self) -> str | None:
        return self._run_id

    def log_params(self, params: dict) -> None:
        if self._sidecar:
            self._sidecar.write({"type": "params", "params": params})
        if not self.live:
            return
        from mlflow.entities import Param

        items = [Param(str(k), str(v)[:500]) for k, v in params.items()]
        for i in range(0, len(items), _PARAM_CHUNK):
            self._safe(
                lambda chunk=items[i : i + _PARAM_CHUNK]: self._client.log_batch(
                    self._run_id, params=chunk
                )
            )

    def log_metrics(self, metrics: dict, step: int | None = None) -> None:
        if self._sidecar:
            self._sidecar.write({"type": "metrics", "step": step, "metrics": metrics})
        if not self.live:
            return
        from mlflow.entities import Metric

        ts = int(time.time() * 1000)
        items = [
            Metric(str(k), float(v), ts, step or 0) for k, v in metrics.items()
        ]
        for i in range(0, len(items), _METRIC_CHUNK):
            self._safe(
                lambda chunk=items[i : i + _METRIC_CHUNK]: self._client.log_batch(
                    self._run_id, metrics=chunk
                )
            )

    def log_artifact(self, local_path: str | Path, artifact_path: str | None = None) -> None:
        if not self.live:
            return
        self._safe(
            lambda: self._client.log_artifact(
                self._run_id, str(local_path), artifact_path
            )
        )

    def log_artifacts(self, local_dir: str | Path, artifact_path: str | None = None) -> None:
        if not self.live:
            return
        self._safe(
            lambda: self._client.log_artifacts(
                self._run_id, str(local_dir), artifact_path
            )
        )

    def set_tags(self, tags: dict) -> None:
        if not self.live:
            return
        for k, v in tags.items():
            self._safe(lambda k=k, v=v: self._client.set_tag(self._run_id, k, str(v)))

    def end(self, status: str = "FINISHED") -> None:
        if self._sidecar:
            self._sidecar.close()
        if self.live:
            self._safe(lambda: self._client.set_terminated(self._run_id, status))

    def _safe(self, operation) -> None:
        try:
            operation()
        except Exception as e:
            logger.warning("Tracking call failed (%s); pipeline continues", e)


class MetricsSidecar:
    """Append-only JSONL metrics record next to the run's artifacts."""

    def __init__(self, run_dir: str | Path):
        path = Path(run_dir)
        path.mkdir(parents=True, exist_ok=True)
        self.path = path / "metrics.jsonl"
        self._fh = open(self.path, "a")

    def write(self, record: dict) -> None:
        record = {"ts": time.time(), **record}
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()


def load_sidecar_metrics(run_dir: str | Path):
    """Read ``metrics.jsonl`` back as a tidy DataFrame (metric, step, value).

    The structured replacement for scraping loss curves out of log text.
    """
    import pandas as pd

    path = Path(run_dir) / "metrics.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"No metrics.jsonl in {run_dir}")
    rows = []
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            if record.get("type") != "metrics":
                continue
            for name, value in record["metrics"].items():
                rows.append(
                    {"metric": name, "step": record.get("step"), "value": value}
                )
    return pd.DataFrame(rows)
