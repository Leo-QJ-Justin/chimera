"""Training pipeline: the orchestrator.

Deliberately thin (R1.5). It owns the split, the run directory and the
artifacts; it does **not** own how any model family is fitted. Everything
model-shaped goes through the trainer built from the ``trainer/`` config
group, so this file has no ``if trainer.kind == ...`` in it and adding a
family never touches it.

    model-input table
      -> split (recorded by stable key + fingerprint)
      -> build_trainer(cfg.trainer)
      -> [optional] trainer.hyperparameter_tune(...)
      -> trainer.train(...)
      -> trainer.evaluate(each split)
      -> trainer.log_model(tracker)  [MLflow flavor, when tracking is live]
      -> post-fit diagnostics (curves, importances, SHAP)
      -> trainer.save(run_dir) + metadata + snapshot + pointers

The middle three steps run one of **two protocols**, chosen by the
family's own ``uses_val_in_fit`` flag rather than by its name (R1.10):

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
anyone reading test.

    outputs/training/<timestamp>/
        <trainer's files>   whatever save() wrote, named in metadata
        splits.json         realized membership by stable key + fingerprints
        metadata.json       the reload envelope (feature order, files, upstream)
        config.yaml         the post-compose config that actually ran
        metrics.jsonl       structured metric sidecar (works with MLflow off)
        plots/              post-fit diagnostic figures (see modules/diagnostics.py)

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

            # Which protocol this run follows is the family's call, never the
            # orchestrator's: each helper below asks the trainer rather than
            # branching on its kind, so adding a family still touches nothing
            # here.
            X_fit, y_fit = self._fit(tracker, trainer, X, y)

            metrics = self._evaluate(tracker, trainer, X, y, X_fit, y_fit)
            self._log_run(tracker, trainer, frames, fingerprints, metrics, len(X_fit))
            self._log_model(tracker, trainer, X_fit)
            self._log_diagnostics(tracker, run_dir, trainer, X["val"])

            with stage_timer("persist", tracker):
                files = trainer.save(run_dir)
                self._save_metadata(
                    run_dir, timestamp, trainer, files, fingerprints, metrics, len(X_fit)
                )
                save_config_snapshot(run_dir, config.model_dump())
            self._update_pointers(timestamp, trainer, metrics)

            # Artifacts last, and the log file after them: it is still being
            # written until this point.
            tracker.log_artifacts(run_dir)
            if self.log_path:
                tracker.log_artifact(self.log_path)
        finally:
            tracker.end()

        logger.info("Training run complete: %s", run_dir)
        return run_dir

    # -------------------------------------------------------------- protocol

    def _fit_frames(self, trainer, X: dict, y: dict) -> tuple:
        """The frames the search and the final fit see, per protocol.

        Standing val: train only, because val has to stay outside the fit
        to referee the early stopping inside it. Pooled: the train+val pool.
        """
        if trainer.uses_val_in_fit:
            return X["train"], y["train"]
        return self._pool(X, y)

    @staticmethod
    def _pool(X: dict, y: dict) -> tuple:
        """train+val concatenated in split order.

        Order matters: a temporal run's pool stays chronological, which is
        what lets a CV fold carve its stopping subset off the end of its own
        training window rather than out of the middle of it.
        """
        return pd.concat([X["train"], X["val"]]), pd.concat([y["train"], y["val"]])

    def _fit(self, tracker, trainer, X: dict, y: dict) -> tuple:
        """Tune (optional) then fit, both on this protocol's frames.

        Returns:
            ``(X_fit, y_fit)`` - the rows the saved model was fitted on,
            which is what the run then reports and records.
        """
        X_fit, y_fit = self._fit_frames(trainer, X, y)
        if self.config.trainer.tune.enabled:
            with stage_timer("tune", tracker):
                self._tune(trainer, X_fit, y_fit)
        with stage_timer("train", tracker):
            if trainer.uses_val_in_fit:
                trainer.train(X_fit, y_fit, X["val"], y["val"])
            else:
                # No validation arguments at all: those rows are inside
                # X_fit now, and handing them over a second time as a
                # "validation split" is how an in-sample number ends up
                # being read as a held-out one.
                trainer.train(X_fit, y_fit)
        return X_fit, y_fit

    def _selection(self, trainer) -> tuple[str, str]:
        """``(basis, metric_key)`` - what ``best.json`` means for this run.

        Standing val selects on the configured split. The pooled protocol
        has no out-of-sample split left to select on (val is in the fit),
        so ``selection.split`` is ignored and the CV estimate decides;
        the ``cv_`` prefix is what keeps the two kinds of number from being
        silently ranked against each other.

        ``selection.basis: cv`` puts every family on the CV basis instead -
        the point being that runs of different families then carry the same
        metric key and *do* rank against each other (R1.11).
        """
        selection = self.config.selection
        if trainer.uses_val_in_fit and selection.basis != "cv":
            return selection.split, f"{selection.split}_{selection.metric}"
        return "cv", f"cv_{selection.metric}"

    # ---------------------------------------------------------------- stages

    def _tune(self, trainer, X_search, y_search) -> None:
        """Search over the protocol's frames: train, or the train+val pool.

        The tuner folds over whatever it is handed, so the protocol is
        expressed here rather than inside it.
        """
        tune = self.config.trainer.tune
        trainer.hyperparameter_tune(
            X_search,
            y_search,
            n_trials=tune.n_trials,
            cv=tune.cv,
            metric=tune.metric,
            direction=tune.direction,
        )

    def _evaluate(self, tracker, trainer, X: dict, y: dict, X_fit, y_fit) -> dict:
        """Score the run, in whichever terms its protocol can defend."""
        if not trainer.uses_val_in_fit:
            return self._evaluate_pool(tracker, trainer, X, y, X_fit, y_fit)
        metrics = self._evaluate_splits(trainer, X, y)
        if self.config.selection.basis == "cv":
            metrics.update(self._comparable_cv(tracker, trainer, X, y))
        return metrics

    def _comparable_cv(self, tracker, trainer, X: dict, y: dict) -> dict[str, float]:
        """The cross-comparable number for a standing-val family (R1.11).

        The fit above is untouched - this family's early stopping still
        needs its standing referee - but the number ``best.json`` records
        becomes a procedure CV over the train+val pool, where each fold
        carves its own referee. That is what a pooled family's ``cv_``
        number already is, so the two rank against each other.
        """
        logger.info(
            "selection.basis=cv: %s keeps its standing-val fit, and best.json "
            "reads a procedure-CV estimate on train+val instead of %s_%s",
            trainer.model_type,
            self.config.selection.split,
            self.config.selection.metric,
        )
        return self._cv_estimate(tracker, trainer, *self._pool(X, y))

    def _evaluate_splits(self, trainer, X: dict, y: dict) -> dict[str, float]:
        """Score every split; train included as the overfitting reference."""
        metrics: dict[str, float] = {}
        for name in ("train", "val", "test"):
            split_metrics = trainer.evaluate(X[name], y[name])
            log_metrics(split_metrics, name)
            metrics.update(prefixed(split_metrics, name))
        return metrics

    def _evaluate_pool(self, tracker, trainer, X: dict, y: dict, X_fit, y_fit) -> dict:
        """In-sample ``dev_*``, untouched ``test_*``, and the CV estimate.

        Deliberately no ``val_*`` row: those rows are inside the fit, so a
        metric labelled "val" would be read as held-out when it is not, and
        the label is the whole reason anyone trusts the number. ``dev_*``
        is the pool's in-sample score - the overfitting reference ``train_*``
        was - and the out-of-sample number this protocol has is the CV
        estimate below.
        """
        logger.info(
            "%s does not use val during the fit: pooled protocol, so train+val "
            "is the fit and no val_* metric is emitted",
            trainer.model_type,
        )
        logger.info(
            "selection.split=%r is ignored here; best.json reads the CV "
            "estimate on train+val instead",
            self.config.selection.split,
        )
        metrics: dict[str, float] = {}
        scored = (("dev", X_fit, y_fit), ("test", X["test"], y["test"]))
        for name, frame, target in scored:
            split_metrics = trainer.evaluate(frame, target)
            log_metrics(split_metrics, name)
            metrics.update(prefixed(split_metrics, name))
        metrics.update(self._cv_estimate(tracker, trainer, X_fit, y_fit))
        return metrics

    def _cv_estimate(self, tracker, trainer, X_pool, y_pool) -> dict[str, float]:
        """The CV selection number: the family's own procedure, k times.

        A fresh trainer per fold running the family's real ``train`` (R1.11),
        split by the run's own ``split.mode`` (D9), over the pool - so the
        estimate describes the procedure the run ships, not a cheaper stand-in
        for it. Fold count comes from ``trainer.tune.cv``: it is the run's
        declared CV budget whether or not the search ran.

        The std travels with the mean because a selection criterion is a
        random variable: two runs 0.002 apart on a fold spread of 0.05 have
        not been distinguished (Cawley & Talbot 2010).
        """
        selection = self.config.selection
        folds = self.config.trainer.tune.cv
        with stage_timer("selection_cv", tracker):
            results = trainer.cross_validate(
                X_pool, y_pool, cv=folds, metrics=[selection.metric]
            )
        stats = results[selection.metric]
        logger.info(
            "CV estimate on train+val: %s = %.4f +/- %.4f over %d folds",
            selection.metric,
            stats["mean"],
            stats["std"],
            folds,
        )
        return {
            f"cv_{selection.metric}": stats["mean"],
            f"cv_{selection.metric}_std": stats["std"],
        }

    def _log_run(self, tracker, trainer, frames, fingerprints, metrics, n_fit) -> None:
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
        params["n_fit"] = n_fit
        params["selection_basis"] = self._selection(trainer)[0]
        params["processed_path"] = self.config.processed_path
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
        self, run_dir, timestamp, trainer, files, fingerprints, metrics, n_fit
    ) -> None:
        """Write the reload envelope, embedding the upstream data config."""
        config = self.config
        manifest = load_manifest(config.processed_path)
        basis, metric_key = self._selection(trainer)
        fit_splits = ["train"] if trainer.uses_val_in_fit else ["train", "val"]
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
                "fit_splits": fit_splits,
                "n_fit_rows": n_fit,
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

    def _update_pointers(self, timestamp: str, trainer, metrics: dict) -> None:
        """latest.json always; best.json only on monotonic improvement."""
        selection = self.config.selection
        save_latest_pointer(self.config.output_dir, timestamp)
        metric_key = self._selection(trainer)[1]
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
