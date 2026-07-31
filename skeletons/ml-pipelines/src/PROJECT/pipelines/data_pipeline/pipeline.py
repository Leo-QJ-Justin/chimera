"""Data pipeline: raw -> stateless clean -> stateless features -> processed.

The orchestrator only sequences stages, times them, and offers each stage
boundary to the writer as a checkpoint. The stateless work lives in
``modules/cleaning.py``; the checkpoint mechanism, the output contract,
the manifest and the row counters live in
``classes/dataset_writer.py``.

The output is the **full** dataset: no splitting happens here. It carries
the declared ``key_cols`` so the training pipeline can record split
membership by stable key rather than positional index (D8), plus a
sidecar manifest that the training run embeds as ``upstream_config``.
"""

import logging
from pathlib import Path

from ...core.seeding import set_seed
from ...core.timing import stage_timer
from ...core.tracking import init_tracking
from ...schemas import DataPipelineConfig
from .classes.dataset_writer import DatasetWriter
from .modules.cleaning import clean, engineer_features, load_raw

logger = logging.getLogger(__name__)


class DataPipeline:
    """Orchestrates the stateless half of the data path."""

    def __init__(self, config: DataPipelineConfig, log_path: str | Path | None = None):
        """
        Args:
            config: Validated data pipeline config.
            log_path: The entry script's log file, uploaded as the last
                run artifact so it captures everything before it.
        """
        self.config = config
        self.log_path = log_path

    def run(self) -> Path:
        """Write the model-input table and its manifest.

        Returns:
            The model-input table path.
        """
        config = self.config
        # No randomness today, but this is the head of the data path; a
        # seeded entry keeps that true if a sampling knob is ever added.
        set_seed(config.seed)

        tracker = init_tracking(
            enabled=config.mlflow.enabled,
            tracking_uri=config.mlflow.tracking_uri,
            experiment_name=config.mlflow.experiment_name,
            run_name=config.mlflow.run_name,
            tags={"pipeline": "data"},
        )
        writer = DatasetWriter(config)
        try:
            with stage_timer("load", tracker):
                df = load_raw(config.raw_path, config.date_col)
            writer.checkpoint("raw", df)

            with stage_timer("clean", tracker):
                df, counts = clean(df, config.cleaning, config.key_cols)
            writer.record_counts(counts)
            writer.checkpoint("cleaned", df)

            with stage_timer("engineer_features", tracker):
                df = engineer_features(df, config.features, config.date_col)
            writer.checkpoint("features", df)

            with stage_timer("write_processed", tracker):
                processed_path, manifest = writer.write(df)

            # Row-count reasons are metrics, not log prose: a run that drops
            # 40% of its rows should be visible on a chart, not in a grep.
            tracker.log_params(
                {"raw_path": config.raw_path, "processed_path": str(processed_path)}
            )
            tracker.log_metrics({f"rows_{k}": v for k, v in writer.counts.items()})
            tracker.log_artifact(manifest)
            if self.log_path:
                tracker.log_artifact(self.log_path)
        finally:
            tracker.end()

        return processed_path
