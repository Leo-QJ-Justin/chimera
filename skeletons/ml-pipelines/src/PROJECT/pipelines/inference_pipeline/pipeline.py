"""Inference pipeline: metadata-first reload, one data path.

Resolve a training run, rebuild whatever trainer produced it, enforce the
recorded feature contract, predict, write a predictions file keyed for
downstream joins. That is all it does - **scoring lives in the evaluation
pipeline**, which consumes this file (D4).

The reason for the split is structural, not stylistic: predictions must
be produced exactly once, by the code that serves them. A second
sample-building path for evaluation drifts from the serving path, and the
drift shows up as a train/serve skew nobody can localise.
"""

import logging
from pathlib import Path

import pandas as pd

from ...core.timing import stage_timer
from ...core.tracking import init_tracking
from ...schemas import InferenceConfig
from .classes.model_loader import ModelLoader
from .modules.validation import read_input, validate_features, validate_keys

logger = logging.getLogger(__name__)


class InferencePipeline:
    """Load a recorded run, reproduce its feature contract, predict."""

    def __init__(self, config: InferenceConfig, log_path: str | Path | None = None):
        self.config = config
        self.log_path = log_path

    def run(self) -> Path:
        """Write the predictions file.

        Returns:
            The predictions file path.
        """
        config = self.config
        tracker = init_tracking(
            enabled=config.mlflow.enabled,
            tracking_uri=config.mlflow.tracking_uri,
            experiment_name=config.mlflow.experiment_name,
            run_name=config.mlflow.run_name,
            tags={"pipeline": "inference"},
        )
        try:
            with stage_timer("load_model", tracker):
                # expected=None: this process has not pinned a feature set
                # yet, so the loaded run defines it.
                trainer, metadata = ModelLoader(config.model).load(expected_features=None)

            with stage_timer("load_input", tracker):
                df = read_input(config.input_path)

            X = validate_features(df, metadata["feature_columns"])
            with stage_timer("predict", tracker):
                output = self._build_output(df, X, trainer)

            output_path = self._write_output(output)
            tracker.log_params(
                {
                    "model_type": metadata["model_type"],
                    "run_timestamp": metadata["timestamp"],
                    "input_path": config.input_path,
                    "output_path": str(output_path),
                }
            )
            tracker.log_metrics({"n_predictions": len(output)})
            if self.log_path:
                tracker.log_artifact(self.log_path)
        finally:
            tracker.end()
        return output_path

    def _build_output(self, df: pd.DataFrame, X: pd.DataFrame, trainer) -> pd.DataFrame:
        """Keys + prediction (+ class probabilities), in that order."""
        keys = validate_keys(df, self.config.key_cols)
        output = df[keys].copy() if keys else pd.DataFrame(index=df.index)
        output["prediction"] = trainer.predict(X)

        if self.config.include_probabilities:
            proba = trainer.predict_proba(X)
            classes = trainer.classes_
            if proba is None or classes is None:
                logger.info(
                    "%s exposes no probabilities; writing hard predictions only",
                    trainer.model_type,
                )
            else:
                for i, label in enumerate(classes):
                    output[f"proba_{label}"] = proba[:, i]
        return output

    def _write_output(self, output: pd.DataFrame) -> Path:
        path = Path(self.config.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".parquet":
            output.to_parquet(path, index=False)
        else:
            output.to_csv(path, index=False)
        logger.info("Wrote %d predictions to %s", len(output), path)
        return path
