"""Evaluation pipeline: predictions + ground truth -> report.

The fourth pipeline (R1.2). It consumes what ``run_inference.py``
produced and joins it to the model-input table's labels **by key**, never by row
position: the two files are written by different runs and need not share
an order.

It never builds a sample and never touches a model. That is the one data
path rule (D4) stated as a directory boundary - if this pipeline ever
needs to preprocess something, the preprocessing belongs upstream.

    outputs/evaluation/<timestamp>/
        report.json    metrics, per-class table, error summary, triage rows
        report.md      the same thing, readable, for a PR or a ticket
        metrics.jsonl  structured metric sidecar (works with MLflow off)
"""

import json
import logging
from pathlib import Path

import pandas as pd

from ...core.run_artifacts import (
    generate_timestamp,
    get_best_info,
    make_run_dir,
    make_serialisable,
    save_config_snapshot,
    save_latest_pointer,
)
from ...core.timing import stage_timer
from ...core.tracking import init_tracking
from ...schemas import EvaluationConfig
from .modules.metrics import compute_metrics, log_metrics, per_class_table
from .modules.triage import error_summary, to_markdown, worst_cases

logger = logging.getLogger(__name__)

REPORT_JSON = "report.json"
REPORT_MD = "report.md"


class EvaluationPipeline:
    """Join, score, triage, report."""

    def __init__(self, config: EvaluationConfig, log_path: str | Path | None = None):
        self.config = config
        self.log_path = log_path

    def run(self) -> Path:
        """Write the evaluation report and return its run directory."""
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

            metrics = compute_metrics(
                joined[config.target], joined[config.prediction_col], task=config.task
            )
            log_metrics(metrics, "evaluation")
            tracker.log_metrics(metrics)

            report = self._build_report(joined, metrics, timestamp)
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

    def _join(self) -> pd.DataFrame:
        """Predictions + ground truth, matched on the declared keys.

        Raises:
            KeyError: A key or the target/prediction column is absent.
            ValueError: The join matched nothing, or the model-input table has
                duplicate keys (which would multiply rows silently).
        """
        config = self.config
        predictions = _read(config.predictions_path)
        processed = _read(config.processed_path)

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
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise KeyError(f"{what} is missing required column(s): {missing}")

    # ---------------------------------------------------------------- report

    def _build_report(self, joined: pd.DataFrame, metrics: dict, timestamp: str) -> dict:
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
        same thing - typically this run scored the full model-input table while
        ``best.json`` recorded a validation split. Worth knowing before
        anyone quotes either number.
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
        logger.info(
            "Training recorded %s=%.4f (run %s); this evaluation: %.4f (delta %+.4f)",
            best["metric"],
            best["value"],
            best["timestamp"],
            value,
            delta,
        )
        return {
            "best_run": best["timestamp"],
            "best_metric": best["metric"],
            "best_value": best["value"],
            "evaluation_metric": config.selection_metric,
            "evaluation_value": value,
            "delta": delta,
        }

    def _write_report(self, run_dir: Path, report: dict) -> None:
        triage = report.pop("_triage_frame")
        (run_dir / REPORT_JSON).write_text(
            json.dumps(make_serialisable(report), indent=2)
        )
        (run_dir / REPORT_MD).write_text(self._render_markdown(report, triage))

    def _render_markdown(self, report: dict, triage: pd.DataFrame) -> str:
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
            "",
        ]
        return "\n".join(lines)


def _read(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Evaluation input not found: {path}")
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
