"""Training pipeline: the orchestrator.

It owns the split, the run directory and the artifacts, not how any model
family is fitted. The protocol is expressed by the trainer's own methods;
the orchestrator sequences them and never branches on the family.

    model-input table
      -> split (recorded by stable key + fingerprint)
      -> build_trainer(cfg.trainer)
      -> trainer.fit_frames(X, y)
      -> [optional] trainer.hyperparameter_tune(...)
      -> trainer.train(...)
      -> trainer.evaluate_run(...)
      -> trainer.log_model(tracker)  [MLflow flavor, when tracking is live]
      -> post-fit diagnostics (curves, importances, SHAP)
      -> trainer.save(run_dir) + metadata + snapshot + pointers

The trainer states how its data is shaped (``fit_frames``), what its run may
claim (``evaluate_run``) and what ``best.json`` therefore means
(``selection_key``). A fit with no in-fit stopping criterion never reads a
validation split, so train and val are pooled into the fit and the run
selects on a k-fold CV estimate over the pool; families that early-stop keep
val as a standing referee outside the fit. Membership is recorded in
``splits.json`` under either protocol. ``selection.basis: cv`` puts every
family on the pooled CV yardstick without changing the fit the run ships.

    outputs/training/<timestamp>/
        <trainer's files>   whatever save() wrote, named in metadata
        splits.json         realized membership by stable key + fingerprints
        metadata.json       the reload envelope (feature order, files, upstream)
        config.yaml         the post-compose config that actually ran
        environment.json    interpreter + package versions the run ran under
        metrics.jsonl       structured metric sidecar (works with MLflow off)
        plots/              post-fit diagnostic figures (see modules/diagnostics.py)

plus ``latest.json`` / ``best.json`` pointers at ``outputs/training/``. Runs
are found only through those pointers, never by globbing directories.
"""

import logging
from pathlib import Path

import pandas as pd

from ...core.run_artifacts import (
    file_fingerprint,
    generate_timestamp,
    get_git_info,
    make_run_dir,
    record_environment,
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
from .classes import build_trainer
from .modules.diagnostics import run_diagnostics
from .modules.splitting import record_splits, resolve_feature_columns, split_frame

logger = logging.getLogger(__name__)

# Rows of the training split sent along as the logged model's input example:
# enough for MLflow to infer a signature, few enough not to embed the data.
_MODEL_EXAMPLE_ROWS = 5


class TrainingPipeline:
    """Split -> train -> evaluate -> persist, with one timestamp threaded."""

    def __init__(self, config: TrainingConfig, log_path: str | Path | None = None):
        """Hold the configuration a run is executed from.

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
            # Hashed here rather than copied out of the data pipeline's
            # manifest: the record has to be of what this run actually read,
            # which is the one thing a stale manifest cannot tell it.
            processed_fp = file_fingerprint(config.processed_path)
            logger.info(
                "Model-input table: %d rows x %d cols (content %s)",
                len(df),
                df.shape[1],
                processed_fp,
            )

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

            # The trainer shapes its own fit frames, so the tune and train
            # calls below are unconditional: which protocol the run follows
            # is stated by the family, not chosen here.
            fit = trainer.fit_frames(X, y)
            if config.trainer.tune.enabled:
                with stage_timer("tune", tracker):
                    self._tune(trainer, fit.X_fit, fit.y_fit)
            with stage_timer("train", tracker):
                trainer.train(fit.X_fit, fit.y_fit, fit.X_ref, fit.y_ref)

            # Values, never the config object or the tracker: the trainer
            # scores itself, and this file times the call and logs the result.
            selection = config.selection
            basis, metric_key = trainer.selection_key(
                metric=selection.metric, basis=selection.basis, split=selection.split
            )
            with stage_timer("evaluate", tracker):
                metrics = trainer.evaluate_run(
                    X,
                    y,
                    fit.X_fit,
                    fit.y_fit,
                    metric=selection.metric,
                    cv=config.trainer.tune.cv,
                    basis=selection.basis,
                    split=selection.split,
                )

            self._log_run(
                tracker, trainer, frames, fingerprints, metrics, fit, basis, processed_fp
            )
            self._log_model(tracker, trainer, fit.X_fit)
            self._log_diagnostics(tracker, run_dir, trainer, X["val"])

            with stage_timer("persist", tracker):
                files = trainer.save(run_dir)
                record_environment(run_dir)
                self._save_metadata(
                    run_dir,
                    timestamp,
                    trainer,
                    files,
                    fingerprints,
                    metrics,
                    fit,
                    basis,
                    metric_key,
                    processed_fp,
                )
                save_config_snapshot(run_dir, config.model_dump())
            self._update_pointers(timestamp, metrics, metric_key)

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

    def _tune(self, trainer, X_search, y_search) -> None:
        """Search over the fit frames: train, or the train+val pool.

        Which of the two it is was already decided by the family's own
        ``fit_frames``, and its tuner searches whatever it is handed -
        folding over it, or carving its own referee out of it - so this call
        is the same under either protocol. ``metric`` is a project metric
        alias, and a null ``direction`` is left null so the trainer infers
        it from the metric rather than assuming higher is better.
        """
        tune = self.config.trainer.tune
        trainer.hyperparameter_tune(
            X_search,
            y_search,
            n_trials=tune.n_trials,
            cv=tune.cv,
            metric=tune.metric,
            direction=tune.direction,
            space=tune.space,
        )

    # ---------------------------------------------------- tracking & logging

    def _log_run(
        self,
        tracker,
        trainer,
        frames,
        fingerprints,
        metrics,
        fit,
        basis: str,
        processed_fp: str,
    ) -> None:
        """Params, per-iteration history, and the final metric set."""
        params = trainer.get_params()
        params.update({f"n_{name}": len(frame) for name, frame in frames.items()})
        # Fingerprints let two runs' splits be compared without reopening
        # either splits.json.
        params.update({f"split_fp_{name}": fp for name, fp in fingerprints.items()})
        params["split_mode"] = self.config.split.mode
        # Split sizes above are membership; this is what the final fit saw -
        # n_train under standing val, n_train + n_val when pooled. Two params
        # rather than a redefined n_train, so splits.json and the tracker
        # never disagree about what "train" means.
        params["n_fit"] = len(fit.X_fit)
        params["selection_basis"] = basis
        params["processed_path"] = self.config.processed_path
        # Beside the path: the path says where the run read, the hash says
        # which version of that table it read.
        params["processed_fp"] = processed_fp
        tracker.log_params(params)
        for record in trainer.history:
            step = record.get("epoch")
            tracker.log_metrics({k: v for k, v in record.items() if k != "epoch"}, step)
        tracker.log_metrics(metrics)

    def _log_model(self, tracker, trainer, X_fit) -> None:
        """Log the fitted model in its own MLflow flavor.

        Autolog is deliberately not used: it dumps per-version parameter
        sets nobody curated, fires on every CV and tuning fit rather than
        on the run's model, and cannot attach this run's split
        fingerprints. Each trainer instead logs its own flavor once.

        Tracking failures warn and never abort a run; artifacts already
        written are never lost to a logging error.
        """
        if not tracker.live:
            return
        try:
            trainer.log_model(tracker, X_fit.head(_MODEL_EXAMPLE_ROWS))
        except Exception as e:
            logger.warning("Model logging failed (%s); the run itself is intact", e)

    def _log_diagnostics(self, tracker, run_dir, trainer, X_val) -> None:
        """Post-fit figures for the model itself: curves, importances, SHAP.

        Not the trainer's job - it captures history, it does not draw it -
        and drawn before the run directory is uploaded, so ``plots/`` mirrors
        into MLflow with the rest of the run and needs no tracking code of
        its own. Failures warn, as tracking failures do: a figure that could
        not be drawn must not cost the run its artifacts.

        The validation frame is the attribution sample under either protocol.
        These figures describe how the model behaves on rows, not how well it
        generalises, so explaining rows a pooled fit consumed is not the leak
        that scoring them would be.
        """
        options = self.config.diagnostics
        if not options.enabled:
            logger.info("diagnostics.enabled=false; no post-fit figures written")
            return
        try:
            with stage_timer("diagnostics", tracker):
                run_diagnostics(run_dir, trainer, options, X_val)
        except Exception as e:
            logger.warning("Diagnostics failed (%s); the run itself is intact", e)

    # ----------------------------------------------------------- persistence

    def _save_metadata(
        self,
        run_dir,
        timestamp,
        trainer,
        files,
        fingerprints,
        metrics,
        fit,
        basis: str,
        metric_key: str,
        processed_fp: str,
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
                # What the selection number is: "cv" means best.json holds a
                # k-fold estimate on train+val, not a score on a standing
                # split.
                "selection_basis": basis,
                "selection_metric_key": metric_key,
                # Which splits the final fit consumed, and how many rows: the
                # counterpart to the membership recorded in splits.json.
                "fit_splits": fit.fit_splits,
                "n_fit_rows": len(fit.X_fit),
                "metrics": metrics,
                "trainer": trainer.training_summary(),
                "git": get_git_info(),
                "processed_path": config.processed_path,
                # Path plus content hash is what makes the run replayable
                # without storing its frames: core.splits.load_split_frames
                # rebuilds them from here and splits.json, and refuses if the
                # table at that path is no longer the one this run read.
                "processed_fingerprint": processed_fp,
            },
            files={
                **files,
                "splits": "splits.json",
                "config": "config.yaml",
                "environment": "environment.json",
            },
            # The data-pipeline config that produced the training frame, so
            # inference replays training-time preprocessing regardless of what
            # the YAML says later.
            upstream_config=manifest.get("config") if manifest else None,
            tz=config.timezone,
        )

    def _update_pointers(self, timestamp: str, metrics: dict, metric_key: str) -> None:
        """latest.json always; best.json only on monotonic improvement."""
        selection = self.config.selection
        save_latest_pointer(self.config.output_dir, timestamp)
        try:
            is_best = save_best_pointer(
                self.config.output_dir,
                timestamp,
                value=metrics[metric_key],
                metric=metric_key,
                mode=selection.mode,
            )
        except ValueError as e:
            # A pooled run's cv_* and a standing-val run's val_* estimate
            # different things, so the pointer refuses to rank one against the
            # other. That refusal arrives after the fit, so it warns rather
            # than costing the run everything it already wrote; latest.json
            # still resolves to this run. To rank families in one output_dir,
            # run them all with selection.basis=cv.
            logger.warning("best.json left unchanged: %s", e)
            return
        logger.info(
            "Pointers updated (%s=%.4f, best=%s)",
            metric_key,
            metrics[metric_key],
            is_best,
        )
