"""Evaluation pipeline: predictions + ground truth -> metrics and triage.

No model, no preprocessing, no sample building - it consumes the
inference pipeline's output (D4).
"""

from .pipeline import EvaluationPipeline

__all__ = ["EvaluationPipeline"]
