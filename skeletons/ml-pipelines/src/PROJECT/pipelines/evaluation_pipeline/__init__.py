"""Evaluation pipeline: predictions + ground truth -> metrics and triage.

No model, no preprocessing, no sample building. Predictions are produced
exactly once, by the inference pipeline; evaluation only joins and scores
that file.
"""

from .pipeline import EvaluationPipeline

__all__ = ["EvaluationPipeline"]
