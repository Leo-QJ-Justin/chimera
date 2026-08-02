"""Evaluation pipeline: predictions + ground truth -> report.

The fourth pipeline. It consumes what ``run_inference.py`` produced and
joins it to the model-input table's labels by key, never by row position:
the two files are written by different runs and need not share an order.

It never builds a sample and never touches a model. Predictions are
produced exactly once, by the inference pipeline; evaluation only joins
and scores that file. If this pipeline ever needs to preprocess something,
the preprocessing belongs upstream.

    outputs/evaluation/<timestamp>/
        report.json    metrics, per-class table, error summary, triage rows
        report.md      the same thing, readable, for a PR or a ticket
        metrics.jsonl  structured metric sidecar (works with MLflow off)
        plots/         confusion matrix, ROC/PR/calibration, residuals
"""

import json
import logging
from pathlib import Path

import pandas as pd

from ...core.run_artifacts import (
    file_fingerprint,
    generate_timestamp,
    get_best_info,
    load_metadata,
    make_run_dir,
    make_serialisable,
    read_table,
    resolve_artifact_path,
    save_config_snapshot,
    save_latest_pointer,
)
from ...core.timing import stage_timer
from ...core.tracking import init_tracking
from ...schemas import EvaluationConfig
from .modules.diagnostics import write_evaluation_plots
from .modules.metrics import compute_metrics, log_metrics, per_class_table
from .modules.triage import error_summary, to_markdown, worst_cases

logger = logging.getLogger(__name__)

REPORT_JSON = "report.json"
REPORT_MD = "report.md"


class EvaluationPipeline:
    """Join, score, triage, report."""

    def __init__(self, config: EvaluationConfig, log_path: str | Path | None = None):
        """Initialize the pipeline.

        Args:
            config: Validated evaluation config.
            log_path: The entry script's log file, uploaded as the last
                run artifact so it captures everything before it.
        """
        self.config = config
        self.log_path = log_path

    # ----------------------------------------------------------------- stages

    def run(self) -> Path:
        """Write the evaluation report.

        Returns:
            The run directory the report was written into.
        """
        config = self.config
        timestamp = generate_timestamp(config.timezone)
        run_dir = make_run_dir(config.output_dir, timestamp)
        logger.info("Evaluation run %s -> %s", timestamp, run_dir)

        tracker = init_tracking(
            enabled=config.mlflow.enabled,
            tracking_uri=config.mlflow.tracking_uri,
            experiment_name=config.mlflow.experiment_name,
            run_name=config.mlflow.run_name or timestamp,
            run_dir=run_dir,
            tags={"pipeline": "evaluation"},
        )
        try:
            with stage_timer("join", tracker):
                joined = self._join()
            self._check_data_identity()

            metrics = compute_metrics(
                joined[config.target], joined[config.prediction_col], task=config.task
            )
            # Before the metrics are logged, not after: the curves produce
            # roc_auc/pr_auc, and those belong in the same metric set as
            # everything else rather than in a second, later one.
            plots, curve_metrics = self._write_plots(run_dir, joined)
            metrics.update(curve_metrics)
            log_metrics(metrics, "evaluation")
            tracker.log_metrics(metrics)

            report = self._build_report(joined, metrics, timestamp, plots)
            self._write_report(run_dir, report)
            save_config_snapshot(run_dir, config.model_dump())
            save_latest_pointer(config.output_dir, timestamp)

            tracker.log_params(
                {
                    "predictions_path": config.predictions_path,
                    "processed_path": config.processed_path,
                    "n_rows": len(joined),
                }
            )
            tracker.log_artifacts(run_dir)
            if self.log_path:
                tracker.log_artifact(self.log_path)
        finally:
            tracker.end()

        logger.info("Evaluation report written: %s", run_dir)
        return run_dir

    # ------------------------------------------------------------------ join

    def _check_data_identity(self) -> None:
        """Warn when the ground truth is not the table the model trained on.

        The training run hashed the model-input table it read; this rehashes
        the one being scored against. A mismatch means the file changed
        between the two runs, so every number in the report describes a
        different population than the one the training run published.

        It warns rather than aborts, the same posture the join takes on
        unmatched rows: re-scoring an old model on refreshed data is
        legitimate when deliberate and a defect when accidental, and only
        the reader can tell the two apart.

        The run consulted is the one ``best.json`` names, which is the model
        ``run_inference.py`` loads by default. Silent when there is no
        training run to ask, or when that run predates the fingerprint.
        """
        config = self.config
        try:
            timestamp = get_best_info(config.runs_dir)["timestamp"]
            metadata = load_metadata(resolve_artifact_path(config.runs_dir, timestamp))
        except (FileNotFoundError, KeyError):
            return
        recorded = metadata["training_info"].get("processed_fingerprint")
        if not recorded:
            return
        current = file_fingerprint(config.processed_path)
        if current != recorded:
            logger.warning(
                "Evaluating against different data than the model trained on: "
                "%s now hashes to %s, run %s read %s",
                config.processed_path,
                current,
                timestamp,
                recorded,
            )

    def _join(self) -> pd.DataFrame:
        """Match predictions to ground truth on the declared keys.

        Returns:
            The inner join of the two files, carrying the target, the
            prediction column and any triage drill-down columns.

        Raises:
            KeyError: A key or the target/prediction column is absent.
            ValueError: The join matched nothing, or the model-input table has
                duplicate keys (which would multiply rows silently).
        """
        config = self.config
        predictions = read_table(config.predictions_path)
        processed = read_table(config.processed_path)

        self._require(
            predictions, [*config.key_cols, config.prediction_col], "predictions"
        )
        self._require(processed, [*config.key_cols, config.target], "model-input table")

        if processed.duplicated(subset=config.key_cols).any():
            raise ValueError(
                f"Model-input table has duplicate {config.key_cols}; joining would "
                "multiply prediction rows and inflate every metric"
            )
        truth_cols = [*config.key_cols, config.target, *config.triage.drill_down_columns]
        kept = [c for c in dict.fromkeys(truth_cols) if c in processed.columns]
        truth = processed[kept]
        joined = predictions.merge(truth, on=config.key_cols, how="inner")

        if joined.empty:
            raise ValueError(
                "Predictions and model-input table share no keys - check that both "
                f"were produced with key_cols={config.key_cols}"
            )
        unmatched = len(predictions) - len(joined)
        if unmatched:
            logger.warning(
                "%d of %d predictions have no ground truth and were dropped",
                unmatched,
                len(predictions),
            )
        logger.info("Joined %d predictions to ground truth", len(joined))
        return joined

    @staticmethod
    def _require(frame: pd.DataFrame, columns: list[str], what: str) -> None:
        """Raise a KeyError naming the file that is missing columns."""
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise KeyError(f"{what} is missing required column(s): {missing}")

    # ----------------------------------------------------------------- plots

    def _write_plots(self, run_dir: Path, joined: pd.DataFrame) -> tuple[list, dict]:
        """Draw the report's figures, or log why there are none.

        Failures warn rather than abort, and each figure is guarded
        individually inside the module, so a report missing one figure is
        still written.

        Args:
            run_dir: Directory the figures are written into.
            joined: Predictions joined to ground truth.

        Returns:
            ``(plot_paths, curve_metrics)``; both empty when plotting is
            disabled or failed.
        """
        config = self.config
        if not config.plots.enabled:
            logger.info("plots.enabled=false; the report carries no figures")
            return [], {}
        try:
            return write_evaluation_plots(
                run_dir,
                joined,
                target=config.target,
                prediction_col=config.prediction_col,
                task=config.task,
            )
        except Exception as e:
            logger.warning("Evaluation plots failed (%s); the report is intact", e)
            return [], {}

    # ---------------------------------------------------------------- report

    def _build_report(
        self, joined: pd.DataFrame, metrics: dict, timestamp: str, plots: list
    ) -> dict:
        """Assemble the report payload.

        The triage frame is carried under ``_triage_frame`` for the
        markdown renderer and removed before the JSON is written.

        Args:
            joined: Predictions joined to ground truth.
            metrics: Scalar metrics, including any from the curves.
            timestamp: This evaluation run's timestamp.
            plots: Relative paths of the figures that were written.

        Returns:
            The report payload.
        """
        config = self.config
        triage = worst_cases(
            joined,
            target=config.target,
            prediction_col=config.prediction_col,
            task=config.task,
            top_n=config.triage.top_n,
            key_cols=config.key_cols,
            drill_down_columns=config.triage.drill_down_columns,
        )
        report = {
            "timestamp": timestamp,
            "task": config.task,
            "predictions_path": config.predictions_path,
            "processed_path": config.processed_path,
            "metrics": metrics,
            "error_summary": error_summary(
                joined, config.target, config.prediction_col, config.task
            ),
            "triage": triage.to_dict(orient="records"),
        }
        if plots:
            report["plots"] = plots
        if config.task == "classification":
            report["per_class"] = per_class_table(
                joined[config.target], joined[config.prediction_col]
            ).to_dict(orient="records")
        comparison = self._compare_to_best(metrics)
        if comparison:
            report["comparison"] = comparison
        report["_triage_frame"] = triage
        return report

    def _compare_to_best(self, metrics: dict) -> dict | None:
        """Contrast this report with the value ``best.json`` recorded.

        A large gap usually means the two numbers are not measuring the
        same thing. Typically this run scored the full model-input table
        while ``best.json`` recorded a validation split, or a k-fold CV
        estimate over the train+val pool for a family that pools them. The
        basis travels with the comparison for that reason: the delta is
        only readable once the training number's basis is known.

        Args:
            metrics: This evaluation's metrics.

        Returns:
            The comparison payload, or None when comparison is disabled,
            no best run exists, or the selection metric is absent here.
        """
        config = self.config
        if not config.compare_to_best:
            return None
        try:
            best = get_best_info(config.runs_dir)
        except FileNotFoundError:
            logger.warning("No best.json under %s; skipping comparison", config.runs_dir)
            return None
        value = metrics.get(config.selection_metric)
        if value is None:
            logger.warning(
                "selection_metric=%r absent from this report; skipping comparison",
                config.selection_metric,
            )
            return None
        delta = value - best["value"]
        basis = _describe_basis(best["metric"])
        logger.info(
            "Training recorded %s=%.4f (%s, run %s); this evaluation: %.4f (delta %+.4f)",
            best["metric"],
            best["value"],
            basis,
            best["timestamp"],
            value,
            delta,
        )
        return {
            "best_run": best["timestamp"],
            "best_metric": best["metric"],
            "best_basis": basis,
            "best_value": best["value"],
            "evaluation_metric": config.selection_metric,
            "evaluation_value": value,
            "delta": delta,
        }

    def _write_report(self, run_dir: Path, report: dict) -> None:
        """Write ``report.json`` and its markdown rendering."""
        triage = report.pop("_triage_frame")
        (run_dir / REPORT_JSON).write_text(
            json.dumps(make_serialisable(report), indent=2)
        )
        (run_dir / REPORT_MD).write_text(self._render_markdown(report, triage))

    def _render_markdown(self, report: dict, triage: pd.DataFrame) -> str:
        """Render the report as markdown, section by section."""
        config = self.config
        lines = [
            f"# Evaluation report {report['timestamp']}",
            "",
            f"- task: `{report['task']}`",
            f"- predictions: `{report['predictions_path']}`",
            f"- ground truth: `{report['processed_path']}`",
            "",
            "## Metrics",
            "",
            to_markdown(pd.DataFrame([report["metrics"]])),
            "",
            "## Error summary",
            "",
            to_markdown(pd.DataFrame([report["error_summary"]])),
        ]
        if "per_class" in report:
            lines += [
                "",
                "## Per class",
                "",
                to_markdown(pd.DataFrame(report["per_class"])),
            ]
        if "comparison" in report:
            lines += [
                "",
                "## Against best.json",
                "",
                to_markdown(pd.DataFrame([report["comparison"]])),
            ]
        lines += [
            "",
            f"## Triage: worst {config.triage.top_n}",
            "",
            to_markdown(triage, empty_note="_no errors to triage_"),
        ]
        if "plots" in report:
            # Relative links, so the report reads correctly from inside the run
            # directory and from the MLflow artifact browser alike. Only files
            # that were actually written are listed.
            lines += [
                "",
                "## Plots",
                "",
                *[f"![{Path(p).stem}]({p})" for p in report["plots"]],
            ]
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------- helpers


def _describe_basis(best_metric: str) -> str:
    """Name the kind of number ``best.json`` holds, from its metric key.

    The training pipeline prefixes the key with the basis it selected on
    (``val_``, ``test_``, or ``cv_`` for the pooled protocol), so the
    report can name the basis without loading the training run.

    Args:
        best_metric: Metric key recorded in ``best.json``.

    Returns:
        A phrase describing the basis, for the log line and the report.
    """
    prefix = best_metric.split("_", 1)[0]
    return {
        "cv": "k-fold CV estimate on train+val",
        "val": "the validation split",
        "test": "the test split",
    }.get(prefix, "an unrecognised basis")
