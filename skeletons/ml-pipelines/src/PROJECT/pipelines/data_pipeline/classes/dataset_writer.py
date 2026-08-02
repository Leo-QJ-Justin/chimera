"""Stage checkpoints, the processed table's contract, and its manifest.

Stateful, which is why it is a class and not a function: it accumulates
per-reason row counts across stages, then writes them into the manifest
that the training run embeds as ``upstream_config``. Per-reason counters
are what make a row-count drop interpretable rather than only visible, and
``load_manifest`` is how the training pipeline reads them back.

Stage checkpoints: at each boundary of load -> clean -> engineer features,
the frame can be piped out to ``<checkpoint_dir>/<stage>.parquet``, for
the stages ``checkpoints`` names. They are debugging aids, not inputs -
nothing downstream reads them. The final stage output is the model-input
table at ``processed_path``, the only file the training pipeline consumes,
and the manifest attaches to it.
"""

import json
import logging
from pathlib import Path

import pandas as pd

from ....core.run_artifacts import file_fingerprint, make_serialisable
from ....schemas import DataPipelineConfig

logger = logging.getLogger(__name__)

MANIFEST_SUFFIX = ".manifest.json"


class DatasetWriter:
    """Writes stage checkpoints, then the validated model-input table.

    Args:
        config: The data pipeline's validated config; supplies the key
            columns, the target, which stages to checkpoint and where the
            final table goes.
    """

    def __init__(self, config: DataPipelineConfig):
        self.config = config
        self.counts: dict[str, int] = {}
        self.checkpoints: dict[str, Path] = {}

    def record_counts(self, counts: dict[str, int]) -> None:
        """Merge a stage's per-reason row counters into the run's tally."""
        self.counts.update(counts)

    def checkpoint(self, stage: str, df: pd.DataFrame) -> Path | None:
        """Pipe a stage's output to disk when config asks for it.

        Args:
            stage: Stage name, matched against ``config.checkpoints``.
            df: The frame as that stage left it.

        Returns:
            The written path, or None when the stage is not checkpointed.
        """
        if stage not in self.config.checkpoints:
            return None
        path = Path(self.config.checkpoint_dir) / f"{stage}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        self.checkpoints[stage] = path
        logger.info("Checkpointed stage %r: %d rows -> %s", stage, len(df), path)
        return path

    def check_contract(self, df: pd.DataFrame) -> None:
        """Fail here, not three stages downstream, if keys went missing.

        Args:
            df: The frame about to be written as the model-input table.

        Raises:
            KeyError: A key column or the target did not survive.
            ValueError: Two rows share a key, which would make split
                membership by key ambiguous.
        """
        required = [*self.config.key_cols, self.config.target]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise KeyError(
                f"Processed table is missing required columns {missing}: keys "
                "and target must survive cleaning and feature engineering"
            )
        dupes = int(df.duplicated(subset=self.config.key_cols).sum())
        if dupes:
            raise ValueError(
                f"{dupes} rows share a key ({self.config.key_cols}); split "
                "membership by key would be ambiguous"
            )

    def write(self, df: pd.DataFrame) -> tuple[Path, Path]:
        """Write the model-input table and its manifest sidecar.

        Args:
            df: The final stage output.

        Returns:
            ``(processed_path, manifest_path)``.
        """
        self.check_contract(df)
        processed_path = Path(self.config.processed_path)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(processed_path, index=False)
        written_manifest = self._write_manifest(processed_path, df)
        logger.info(
            "Model-input table written: %s (%d rows x %d cols); manifest %s",
            processed_path,
            len(df),
            df.shape[1],
            written_manifest,
        )
        return processed_path, written_manifest

    def _write_manifest(self, processed_path: Path, df: pd.DataFrame) -> Path:
        """Write the sidecar the training run embeds as ``upstream_config``.

        Metadata-first reload means inference replays this config, not
        whatever the YAML files say months later.

        Returns:
            The written manifest path.
        """
        manifest = {
            "processed_path": str(processed_path),
            # Content identity for the table just written: a path says where
            # a training run looked, this says what it found there.
            "content_hash": file_fingerprint(processed_path),
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
            "key_cols": self.config.key_cols,
            "target": self.config.target,
            "row_counts": self.counts,
            "stage_checkpoints": {k: str(v) for k, v in self.checkpoints.items()},
            "config": self.config.model_dump(),
        }
        path = manifest_path(processed_path)
        path.write_text(json.dumps(make_serialisable(manifest), indent=2))
        return path


def manifest_path(processed_path: str | Path) -> Path:
    """``data/processed/model_input.parquet`` -> ``...model_input.manifest.json``."""
    processed_path = Path(processed_path)
    return processed_path.with_name(processed_path.stem + MANIFEST_SUFFIX)


def load_manifest(processed_path: str | Path) -> dict | None:
    """Read the manifest if the data pipeline produced one."""
    path = manifest_path(processed_path)
    if not path.exists():
        logger.warning("No manifest beside %s; upstream config unknown", processed_path)
        return None
    return json.loads(path.read_text())
