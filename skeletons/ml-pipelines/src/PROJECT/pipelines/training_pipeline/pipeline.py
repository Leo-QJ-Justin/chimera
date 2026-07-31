"""Training pipeline: the orchestrator.

Deliberately thin (R1.5). It owns the split, the run directory and the
artifacts; it does **not** own how any model family is fitted. Everything
model-shaped goes through the trainer built from the ``trainer/`` config
group, so this file has no ``if trainer.name == ...`` in it and adding a
family never touches it.

    model-input table
      -> split (recorded by stable key + fingerprint)
      -> build_trainer(cfg.trainer)
      -> [optional] trainer.hyperparameter_tune(...)
      -> trainer.train(train, val)
      -> trainer.evaluate(each split)
      -> trainer.save(run_dir) + metadata + snapshot + pointers

    outputs/training/<timestamp>/
        <trainer's files>   whatever save() wrote, named in metadata
        splits.json         realized membership by stable key + fingerprints
        metadata.json       the reload envelope (feature order, files, upstream)
        config.yaml         the post-compose config that actually ran
        metrics.jsonl       structured metric sidecar (works with MLflow off)

plus ``latest.json`` / ``best.json`` pointers at ``outputs/training/``,
which are the only supported way to find a run (D10).
"""

import logging
from pathlib import Path

import pandas as pd

from ...core.run_artifacts import (
    generate_timestamp,
    get_git_info,
    make_run_dir,
    save_best_pointer,
    save_config_snapshot,
    save_latest_pointer,
    save_metadata,
)
from ...core.seeding import set_seed
from ...core.timing import stage_timer
from ...core.tracking import init_tracking
from ...schemas import TrainingConfig
from ..data_pipeline.classes.dataset_writer import load_manifest
from ..evaluation_pipeline.modules.metrics import log_metrics, prefixed
from .classes.registry import build_trainer
from .modules.splitting import record_splits, resolve_feature_columns, split_frame

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """Split -> train -> evaluate -> persist, with one timestamp threaded."""

    def __init__(self, config: TrainingConfig, log_path: str | Path | None = None):
        """
        Args:
            config: Validated training config.
            log_path: The entry script's log file, uploaded as the last
                run artifact so it captures everything before it.
        """
        self.config = config
        self.log_path = log_path

    def run(self) -> Path:
        """Execute the run and return its run directory."""
        config = self.config
        set_seed(config.seed)
        timestamp = generate_timestamp(config.timezone)
        run_dir = make_run_dir(config.output_dir, timestamp)
        logger.info("Training run %s -> %s", timestamp, run_dir)

        tracker = init_tracking(
            enabled=config.mlflow.enabled,
            tracking_uri=config.mlflow.tracking_uri,
            experiment_name=config.mlflow.experiment_name,
            run_name=config.mlflow.run_name or timestamp,
            run_dir=run_dir,
            tags={"pipeline": "training", "trainer": config.trainer.kind},
        )
        try:
            with stage_timer("load_processed", tracker):
                df = pd.read_parquet(config.processed_path)
            logger.info("Model-input table: %d rows x %d cols", len(df), df.shape[1])

            numeric, categorical = resolve_feature_columns(df, config)
            trainer = build_trainer(
                config.trainer,
                task=config.task,
                seed=config.seed,
                numeric_features=numeric,
                categorical_features=categorical,
                cv_mode=config.split.mode,
            )
            if not trainer.feature_columns:
                raise ValueError("No feature columns resolved; check training.yaml")

            with stage_timer("split", tracker):
                frames = split_frame(df, config.split, config.target)
            fingerprints = record_splits(run_dir, frames, config.split)

            X = {name: frame[trainer.feature_columns] for name, frame in frames.items()}
            y = {name: frame[config.target] for name, frame in frames.items()}

            if config.trainer.tune.enabled:
                with stage_timer("tune", tracker):
                    self._tune(trainer, X["train"], y["train"])

            with stage_timer("train", tracker):
                trainer.train(X["train"], y["train"], X["val"], y["val"])

            metrics = self._evaluate(trainer, X, y)
            self._log_run(tracker, trainer, frames, fingerprints, metrics)

            with stage_timer("persist", tracker):
                files = trainer.save(run_dir)
                self._save_metadata(
                    run_dir, timestamp, trainer, files, fingerprints, metrics
                )
                save_config_snapshot(run_dir, config.model_dump())
            self._update_pointers(timestamp, metrics)

            # Artifacts last, and the log file after them: it is still being
            # written until this point.
            tracker.log_artifacts(run_dir)
            if self.log_path:
                tracker.log_artifact(self.log_path)
        finally:
            tracker.end()

        logger.info("Training run complete: %s", run_dir)
        return run_dir

    # ---------------------------------------------------------------- stages

    def _tune(self, trainer, X_train, y_train) -> None:
        """Search on the training split only - val stays a clean referee."""
        tune = self.config.trainer.tune
        trainer.hyperparameter_tune(
            X_train,
            y_train,
            n_trials=tune.n_trials,
            cv=tune.cv,
            metric=tune.metric,
            direction=tune.direction,
        )

    def _evaluate(self, trainer, X: dict, y: dict) -> dict[str, float]:
        """Score every split; train included as the overfitting reference."""
        metrics: dict[str, float] = {}
        for name in ("train", "val", "test"):
            split_metrics = trainer.evaluate(X[name], y[name])
            log_metrics(split_metrics, name)
            metrics.update(prefixed(split_metrics, name))
        return metrics

    def _log_run(self, tracker, trainer, frames, fingerprints, metrics) -> None:
        """Params, per-iteration history, and the final metric set."""
        params = trainer.get_params()
        params.update({f"n_{name}": len(frame) for name, frame in frames.items()})
        # Fingerprints make "is this the same split as last week?" a glance.
        params.update({f"split_fp_{name}": fp for name, fp in fingerprints.items()})
        params["split_mode"] = self.config.split.mode
        params["processed_path"] = self.config.processed_path
        tracker.log_params(params)
        for record in trainer.history:
            step = record.get("epoch")
            tracker.log_metrics({k: v for k, v in record.items() if k != "epoch"}, step)
        tracker.log_metrics(metrics)

    # ----------------------------------------------------------- persistence

    def _save_metadata(
        self, run_dir, timestamp, trainer, files, fingerprints, metrics
    ) -> None:
        """Write the reload envelope, embedding the upstream data config."""
        config = self.config
        manifest = load_manifest(config.processed_path)
        save_metadata(
            run_dir=run_dir,
            model_type=trainer.model_type,
            timestamp=timestamp,
            feature_columns=trainer.feature_columns,
            target_columns=[config.target],
            # The trainer's own config round-trip: this is what load() reads.
            hyperparameters=trainer.spec(),
            training_info={
                "task": config.task,
                "split": config.split.model_dump(),
                "split_fingerprints": fingerprints,
                "selection": config.selection.model_dump(),
                "metrics": metrics,
                "trainer": trainer.training_summary(),
                "git": get_git_info(),
                "processed_path": config.processed_path,
            },
            files={**files, "splits": "splits.json", "config": "config.yaml"},
            # The data-pipeline config that produced the training frame, so
            # inference replays training-time preprocessing regardless of what
            # the YAML says later (D10).
            upstream_config=manifest.get("config") if manifest else None,
            tz=config.timezone,
        )

    def _update_pointers(self, timestamp: str, metrics: dict[str, float]) -> None:
        """latest.json always; best.json only on monotonic improvement."""
        selection = self.config.selection
        save_latest_pointer(self.config.output_dir, timestamp)
        metric_key = f"{selection.split}_{selection.metric}"
        is_best = save_best_pointer(
            self.config.output_dir,
            timestamp,
            value=metrics[metric_key],
            metric=metric_key,
            mode=selection.mode,
        )
        logger.info(
            "Pointers updated (%s=%.4f, best=%s)",
            metric_key,
            metrics[metric_key],
            is_best,
        )
