"""MLflow-optional experiment tracking with a structured local sidecar.

Contract:

- Tracking failures warn and never abort a run; artifacts already written
  are never lost to a logging error.
- ``init_tracking`` checks ``enabled`` and the mlflow import inside the
  factory and returns a no-op tracker when either is off, so call sites
  never branch.
- Keyword arguments pass through unfiltered: a wrong kwarg raises in the
  wrapped call and is logged rather than dropped silently.
- Every metric also lands in ``<run_dir>/metrics.jsonl``, so curves are
  recoverable without a tracking server and without parsing log text.
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
    """Build a tracker, resolving the enabled flag and the mlflow import.

    The classic ``./mlruns`` file store is in maintenance mode on MLflow
    3.x and raises at init unless ``MLFLOW_ALLOW_FILE_STORE`` is set; the
    sqlite default works everywhere. Browse it with
    ``mlflow ui --backend-store-uri sqlite:///mlflow.db``.

    Args:
        enabled: Whether to attempt a live MLflow connection at all.
        tracking_uri: Backend store the MLflow client connects to.
        experiment_name: Experiment to log under; created if missing and
            restored if previously deleted.
        run_name: Display name for the created run.
        run_dir: Run artifact directory. When given, the JSONL metrics
            sidecar is written there even if MLflow is off.
        tags: Tags applied at run creation.

    Returns:
        A live MLflow-backed tracker, or a no-op tracker when tracking is
        disabled, mlflow is missing, or initialization fails. The sidecar
        stays active in the no-op case whenever ``run_dir`` was given.
    """
    sidecar = MetricsSidecar(run_dir) if run_dir else None
    if not enabled:
        return Tracker(None, None, sidecar)
    try:
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
    """Uniform tracking surface that no-ops cleanly when not live.

    Every method is safe to call unconditionally. Calls that reach MLflow
    are wrapped so a backend failure warns and returns instead of
    propagating into the pipeline.
    """

    def __init__(self, client, run_id: str | None, sidecar: "MetricsSidecar | None"):
        self._client = client
        self._run_id = run_id
        self._sidecar = sidecar

    @property
    def live(self) -> bool:
        """Whether an MLflow client is attached."""
        return self._client is not None

    @property
    def run_id(self) -> str | None:
        """MLflow run id, or ``None`` when tracking is not live."""
        return self._run_id

    def log_params(self, params: dict) -> None:
        """Record run parameters, batched to stay under MLflow's limits.

        Values are stringified and truncated to 500 characters, so a
        large object never fails the call.

        Args:
            params: Parameter name to value.
        """
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
        """Record scalar metrics, batched, and mirror them to the sidecar.

        Args:
            metrics: Metric name to numeric value.
            step: Step index for curve-shaped metrics; ``0`` when omitted.
        """
        if self._sidecar:
            self._sidecar.write({"type": "metrics", "step": step, "metrics": metrics})
        if not self.live:
            return
        from mlflow.entities import Metric

        ts = int(time.time() * 1000)
        items = [Metric(str(k), float(v), ts, step or 0) for k, v in metrics.items()]
        for i in range(0, len(items), _METRIC_CHUNK):
            self._safe(
                lambda chunk=items[i : i + _METRIC_CHUNK]: self._client.log_batch(
                    self._run_id, metrics=chunk
                )
            )

    def log_artifact(
        self, local_path: str | Path, artifact_path: str | None = None
    ) -> None:
        """Upload a single file to the run's artifact store.

        Args:
            local_path: File to upload.
            artifact_path: Destination directory within the run's
                artifacts; the root when omitted.
        """
        if not self.live:
            return
        self._safe(
            lambda: self._client.log_artifact(
                self._run_id, str(local_path), artifact_path
            )
        )

    def log_artifacts(
        self, local_dir: str | Path, artifact_path: str | None = None
    ) -> None:
        """Upload a directory tree to the run's artifact store.

        Args:
            local_dir: Directory whose contents are uploaded.
            artifact_path: Destination directory within the run's
                artifacts; the root when omitted.
        """
        if not self.live:
            return
        self._safe(
            lambda: self._client.log_artifacts(
                self._run_id, str(local_dir), artifact_path
            )
        )

    def set_tags(self, tags: dict) -> None:
        """Set run tags one at a time, so one bad tag cannot lose the rest.

        Args:
            tags: Tag name to value; values are stringified.
        """
        if not self.live:
            return
        for k, v in tags.items():
            self._safe(lambda k=k, v=v: self._client.set_tag(self._run_id, k, str(v)))

    def end(self, status: str = "FINISHED") -> None:
        """Close the sidecar and terminate the MLflow run.

        Args:
            status: Terminal MLflow run status, such as ``"FINISHED"`` or
                ``"FAILED"``.
        """
        if self._sidecar:
            self._sidecar.close()
        if self.live:
            self._safe(lambda: self._client.set_terminated(self._run_id, status))

    def _safe(self, operation) -> None:
        """Run a tracking call, downgrading any failure to a warning."""
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
        """Append one timestamped record and flush it.

        Flushing per record keeps the file readable while a long run is
        still in progress.

        Args:
            record: JSON-serializable payload; a ``ts`` field is added.
        """
        record = {"ts": time.time(), **record}
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()

    def close(self) -> None:
        """Close the underlying file handle if it is still open."""
        if not self._fh.closed:
            self._fh.close()


def load_sidecar_metrics(run_dir: str | Path):
    """Read ``metrics.jsonl`` back as a tidy DataFrame.

    Args:
        run_dir: Run directory containing ``metrics.jsonl``.

    Returns:
        One row per logged metric value, with columns ``metric``,
        ``step`` and ``value``. Non-metric records are skipped.

    Raises:
        FileNotFoundError: If the run directory has no sidecar file.
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
                rows.append({"metric": name, "step": record.get("step"), "value": value})
    return pd.DataFrame(rows)
