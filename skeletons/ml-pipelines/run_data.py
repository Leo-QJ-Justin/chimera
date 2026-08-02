"""Entry point: data pipeline (raw -> model-input table).

    python run_data.py
    python run_data.py raw_path=data/raw/other.csv cleaning.drop_duplicates=false
    python run_data.py '+checkpoints=[raw,cleaned,features]'

Each pipeline owns its configs beside its code; the shared block
(seed, timezone, logging, mlflow) is pulled in from the repo-root
``configs/`` via ``hydra.searchpath``, so run this from the project root.

``bootstrap`` validates the composed config and configures logging once,
here, before any pipeline code runs.
"""

import sys
from pathlib import Path

import hydra
from omegaconf import DictConfig

# src layout without requiring an editable install: entry scripts are the
# only place that needs to know where the package lives. After `uv sync`
# installs the project, this line is a harmless no-op.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from PROJECT.pipelines.data_pipeline import DataPipeline  # noqa: E402
from PROJECT.schemas import DataPipelineConfig, bootstrap  # noqa: E402

CONFIG_PATH = "src/PROJECT/pipelines/data_pipeline/configs"


@hydra.main(version_base=None, config_path=CONFIG_PATH, config_name="data_pipeline")
def main(cfg: DictConfig) -> None:
    """Validate the composed config and run the data pipeline."""
    config, log_path = bootstrap(cfg, DataPipelineConfig)
    DataPipeline(config, log_path=log_path).run()


if __name__ == "__main__":
    main()
