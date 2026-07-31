"""Entry point: inference pipeline (input + saved run -> predictions).

    python run_inference.py
    python run_inference.py model.use=latest
    python run_inference.py model.timestamp=20260730_143000 input_path=data/raw/new.csv

Metadata-first: the resolved run's ``metadata.json`` names its trainer, its
files and its exact feature order, so this entry point is identical
whether the run was trained by the sklearn, LightGBM or torch trainer.

Scoring lives in ``run_evaluation.py``, which consumes this pipeline's
output. That is the one-data-path rule (D4): predictions are produced
here, once, by the code that serves them.
"""

import sys
from pathlib import Path

import hydra
from omegaconf import DictConfig

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from PROJECT.pipelines.inference_pipeline import InferencePipeline  # noqa: E402
from PROJECT.schemas import InferenceConfig, bootstrap  # noqa: E402

CONFIG_PATH = "src/PROJECT/pipelines/inference_pipeline/configs"


@hydra.main(version_base=None, config_path=CONFIG_PATH, config_name="inference")
def main(cfg: DictConfig) -> None:
    config, log_path = bootstrap(cfg, InferenceConfig)
    InferencePipeline(config, log_path=log_path).run()


if __name__ == "__main__":
    main()
