"""Entry point: evaluation pipeline (predictions + ground truth -> report).

    python run_evaluation.py
    python run_evaluation.py predictions_path=outputs/inference/holdout.parquet
    python run_evaluation.py triage.top_n=50 '+triage.drill_down_columns=[num_a]'

Runs *after* ``run_inference.py``: it joins that pipeline's predictions to
the model-input table's ground truth by key, computes the metric report
and the error triage table, and writes both to
``outputs/evaluation/<timestamp>/``.
"""

import sys
from pathlib import Path

import hydra
from omegaconf import DictConfig

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from PROJECT.pipelines.evaluation_pipeline import EvaluationPipeline  # noqa: E402
from PROJECT.schemas import EvaluationConfig, bootstrap  # noqa: E402

CONFIG_PATH = "src/PROJECT/pipelines/evaluation_pipeline/configs"


@hydra.main(version_base=None, config_path=CONFIG_PATH, config_name="evaluation")
def main(cfg: DictConfig) -> None:
    config, log_path = bootstrap(cfg, EvaluationConfig)
    EvaluationPipeline(config, log_path=log_path).run()


if __name__ == "__main__":
    main()
