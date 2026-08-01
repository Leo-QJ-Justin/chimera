"""Training pipeline: the orchestrator.

Deliberately thin (R1.5). It owns the split, the run directory and the
artifacts; it does **not** own how any model family is fitted. Everything
model-shaped goes through the trainer built from the ``trainer/`` config
group, so this file has no ``if trainer.kind == ...`` in it and adding a
family never touches it.

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

The middle four steps run one of **two protocols**, and which one is the
family's own statement rather than this file's (R1.10, R1.13). The trainer
says how its data is shaped (``fit_frames``), what its run may claim
(``evaluate_run``) and what ``best.json`` therefore means
(``selection_key``); the calls below are the same three whichever family
was built.

- **standing val** (lightgbm, xgboost, torch): tune on train, fit on train
  with val as the live referee their early stopping needs, score
  train/val/test, select on ``selection.split``.
- **pooled** (logreg, random_forest): a family that never reads val during
  the fit has no reason to keep 15% of the data out of it, so tuning folds
  over train+val, the final fit is on that pool, scores are ``dev_*``
  (in-sample on the pool) and ``test_*``, and the selection number is a
  k-fold CV estimate on the pool, logged as ``cv_<metric>``.

Both record train/val/test membership in ``splits.json`` either way: the
pool is built at fit time and the split is still the reproducible record.

``selection.basis: cv`` overlays one thing on top of that (R1.11): a
standing-val family still fits exactly as above - its early stopping needs
the referee - but it *also* runs a procedure CV on train+val and selects on
that, so its ``best.json`` number is the same yardstick a pooled family's
is and the two families can be ranked in one output directory without
anyone reading test. That overlay is the trainer's to apply too: the basis
arrives as a value it reads, not as a branch taken out here.

    outputs/training/<timestamp>/
        <trainer's files>   whatever save() wrote, named in metadata
        splits.json         realized membership by stable key + fingerprints
        metadata.json       the reload envelope (feature order, files, upstream)
        config.yaml         the post-compose config that actually ran
        environment.json    interpreter + package versions the run ran under
        metrics.jsonl       structured metric sidecar (works with MLflow off)
        plots/              post-fit diagnostic figures (see modules/diagnostics.py)

plus ``latest.json`` / ``best.json`` pointers at ``outputs/training/``,
which are the only supported way to find a run (D10).
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

# Rows of the training split sent along as the logged model's input example.
# Enough to infer a signature, few enough to stay a sample.
_MODEL_EXAMPLE_ROWS = 5


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

            # Which protocol this run follows is the family's call, never the
            # orchestrator's: the trainer shapes its own fit frames, so the
            # tune and train calls below are unconditional and adding a
            # family still touches nothing here.
            fit = trainer.fit_frames(X, y)
            if config.trainer.tune.enabled:
                with stage_timer("tune", tracker):
                    self._tune(trainer, fit.X_fit, fit.y_fit)
            with stage_timer("train", tracker):
                trainer.train(fit.X_fit, fit.y_fit, fit.X_ref, fit.y_ref)

            # Values, never the config object or the tracker: a trainer scores
            # itself and this file times the call and logs what comes back.
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
        # Fingerprints make "is this the same split as last week?" a glance.
        params.update({f"split_fp_{name}": fp for name, fp in fingerprints.items()})
        params["split_mode"] = self.config.split.mode
        # Split sizes above are membership; this is what the final fit saw -
        # n_train under standing val, n_train + n_val when pooled. Two params
        # rather than a redefined n_train, so splits.json and the tracker
        # never disagree about what "train" means.
        params["n_fit"] = len(fit.X_fit)
        params["selection_basis"] = basis
        params["processed_path"] = self.config.processed_path
        # Beside the path, because the path alone answers "where did this run
        # read?" and not "was it the same table as last week's run?".
        params["processed_fp"] = processed_fp
        tracker.log_params(params)
        for record in trainer.history:
            step = record.get("epoch")
            tracker.log_metrics({k: v for k, v in record.items() if k != "epoch"}, step)
        tracker.log_metrics(metrics)

    def _log_model(self, tracker, trainer, X_fit) -> None:
        """Log the fitted model in its own MLflow flavor, curated (D3).

        Autolog is deliberately not used: it dumps per-version parameter
        sets nobody curated, fires on every CV and tuning fit rather than
        on the run's model, and cannot attach this run's split
        fingerprints. Each trainer instead logs its own flavor once.

        Failures warn: a model that could not be logged must not cost the
        run the artifacts it already wrote (core tracking contract).
        """
        if not tracker.live:
            return
        try:
            trainer.log_model(tracker, X_fit.head(_MODEL_EXAMPLE_ROWS))
        except Exception as e:
            logger.warning("Model logging failed (%s); the run itself is intact", e)

    def _log_diagnostics(self, tracker, run_dir, trainer, X_val) -> None:
        """Post-fit figures for the model itself: curves, importances, SHAP.

        Deliberately *not* the trainer's job (it captures history, it does
        not draw it) and deliberately before the run directory is uploaded,
        so ``plots/`` mirrors into MLflow with the rest of the run and needs
        no tracking code of its own.

        Failures warn, for the same reason model logging's do: a figure that
        could not be drawn must not cost the run its artifacts.

        The validation frame is the attribution sample under either protocol:
        these figures describe how the model behaves on rows, not how well it
        generalises, so a pooled run explaining rows it was fitted on is not
        the same mistake as scoring them.
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
                # What the selection number actually is, for anyone reading
                # this run months later: "cv" means best.json holds a k-fold
                # estimate on train+val, not a score on a standing split.
                "selection_basis": basis,
                "selection_metric_key": metric_key,
                # Which splits the final fit consumed, and how many rows -
                # the honest counterpart to splits.json's membership.
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
            # the YAML says later (D10).
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
            # different things, and the pointer refuses to rank one against
            # the other - correctly. But that refusal arrives after the fit,
            # so it warns rather than costing the run everything it already
            # wrote; latest.json still resolves to this run. To rank families
            # in one output_dir, run them all with selection.basis=cv (R1.11).
            logger.warning("best.json left unchanged: %s", e)
            return
        logger.info(
            "Pointers updated (%s=%.4f, best=%s)",
            metric_key,
            metrics[metric_key],
            is_best,
        )
