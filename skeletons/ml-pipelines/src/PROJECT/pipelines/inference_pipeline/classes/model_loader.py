"""Run resolution and metadata-first model loading.

The one place that turns "which run?" into a loaded, ready trainer. It is
stateful (it holds a resolved run dir, its metadata and the loaded
trainer), which is why it is a class.

**Trainer-agnostic by construction.** ``metadata.json`` records
``model_type``, which is the trainer family key; the registry maps it to a
trainer class and that class's own ``load`` does the rest. A LightGBM run
and a torch run therefore load through identical code here - which is the
whole point of the ``BaseTrainer`` contract, and the thing that would
quietly rot if this module ever grew a branch on model family.
"""

import logging
from pathlib import Path

from ....core.run_artifacts import (
    get_best_info,
    get_latest_timestamp,
    load_metadata,
    resolve_artifact_path,
    validate_feature_columns,
)
from ...training_pipeline.classes import get_trainer_class

logger = logging.getLogger(__name__)


class ModelLoader:
    """Resolves a training run and rebuilds its trainer.

    Args:
        selection: The ``model`` section of the inference config
            (``use``, ``timestamp``, ``runs_dir``).
    """

    def __init__(self, selection):
        self.selection = selection
        self.run_dir: Path | None = None
        self.metadata: dict | None = None

    def load(self, expected_features: list[str] | None = None):
        """Resolve, validate and load.

        Args:
            expected_features: A feature contract this process has already
                pinned; None lets the loaded run define it.

        Returns:
            ``(trainer, metadata)`` - a fitted :class:`BaseTrainer` and
            the run's metadata envelope.
        """
        self.run_dir = self.resolve_run_dir()
        self.metadata = load_metadata(self.run_dir)
        feature_columns = validate_feature_columns(self.metadata, expected_features)
        trainer_cls = get_trainer_class(self.metadata["model_type"])
        trainer = trainer_cls.load(self.run_dir)
        logger.info(
            "Serving run %s (%s via %s, %d features)",
            self.metadata["timestamp"],
            self.metadata["model_type"],
            trainer_cls.__name__,
            len(feature_columns),
        )
        return trainer, self.metadata

    def resolve_run_dir(self) -> Path:
        """Explicit timestamp > best.json > latest.json, and say which."""
        selection = self.selection
        base = selection.runs_dir
        if selection.timestamp:
            logger.info("Using explicitly requested run %s", selection.timestamp)
            return resolve_artifact_path(base, selection.timestamp)
        if selection.use == "best":
            try:
                timestamp = get_best_info(base)["timestamp"]
            except FileNotFoundError:
                # Falling back is reasonable; doing it silently is not - the
                # corpus bug was a "best" model that was quietly the latest.
                logger.warning("No best.json under %s; falling back to latest", base)
                timestamp = get_latest_timestamp(base)
        else:
            timestamp = get_latest_timestamp(base)
        logger.info("Resolved %s run to %s", selection.use, timestamp)
        return resolve_artifact_path(base, timestamp)
