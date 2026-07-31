"""Entry point: training pipeline (model-input table -> run directory).

    python run_training.py
    python run_training.py trainer=logreg
    python run_training.py trainer=mlp trainer.torch.epochs=50
    python run_training.py trainer=lightgbm trainer.tune.enabled=true
    python run_training.py split.mode=temporal
    python run_training.py mlflow.enabled=false

The ``trainer`` config group selects the model family *and* its harness:
each ``training_pipeline/configs/trainer/<name>.yaml`` declares
``kind: sklearn|lightgbm|torch``, and the pipeline trains whatever the
registry returns. Nothing in the orchestrator branches on family.

The log path returned by ``bootstrap`` is handed to the pipeline so the
run can upload its own log file as the final MLflow artifact.
"""

import sys
from pathlib import Path

import hydra
from omegaconf import DictConfig

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from PROJECT.pipelines.training_pipeline import TrainingPipeline  # noqa: E402
from PROJECT.schemas import TrainingConfig, bootstrap  # noqa: E402

CONFIG_PATH = "src/PROJECT/pipelines/training_pipeline/configs"


@hydra.main(version_base=None, config_path=CONFIG_PATH, config_name="training")
def main(cfg: DictConfig) -> None:
    config, log_path = bootstrap(cfg, TrainingConfig)
    TrainingPipeline(config, log_path=log_path).run()


if __name__ == "__main__":
    main()
