"""Curated MLflow model logging, one flavor per trainer family.

Stateless, so it lives here rather than in ``classes/``: the trainers own
*which* flavor and *what* to hand it; this module owns the mechanics.

Two rules encoded here, both load-bearing:

- **``save_model`` + ``log_artifacts``, never the fluent ``log_model``.**
  The core Tracker drives ``MlflowClient`` with an explicit ``run_id``
  precisely so no pipeline depends on fluent global state (``mlflow.``
  ``start_run`` and friends); reaching for the fluent API here would
  reintroduce exactly what that avoided, and would log to whatever run
  happened to be active.
- **Failures warn.** Tracking failures warn and never abort a run;
  artifacts already written are never lost to a logging error.
"""

import importlib
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# mlflow.<flavor>.save_model spells its model argument differently per flavor.
FLAVOR_ARG = {
    "sklearn": "sk_model",
    "lightgbm": "lgb_model",
    "xgboost": "xgb_model",
    "pytorch": "pytorch_model",
}

# MLflow >= 3.15 defaults sklearn serialisation to skops, which refuses a
# pipeline whose transformers reference types outside its allow-list (a bare
# ColumnTransformer already trips it). Cloudpickle is the long-standing
# format every supported MLflow version reads and writes.
FLAVOR_KWARGS = {
    "sklearn": {"serialization_format": "cloudpickle"},
}


def log_flavor_model(
    tracker, flavor: str, model, *, input_example=None, predictions=None
) -> None:
    """Save ``model`` in an MLflow flavor and upload it as the run's ``model/``.

    Args:
        tracker: The run's :class:`~PROJECT.core.tracking.Tracker`. A no-op
            tracker returns immediately, so call sites never branch.
        flavor: An ``mlflow`` submodule name from :data:`FLAVOR_ARG`.
        model: The object that flavor serialises.
        input_example: A few rows *in the form this flavor's model accepts*
            - transformed, where the flavor stores a bare booster or module
            rather than a pipeline.
        predictions: ``model``'s output for ``input_example``; used only to
            infer the output half of the signature.
    """
    if not getattr(tracker, "live", False):
        return
    try:
        module = importlib.import_module(f"mlflow.{flavor}")
    except ImportError:
        logger.warning("mlflow.%s unavailable; no model artifact logged", flavor)
        return
    try:
        with tempfile.TemporaryDirectory() as scratch:
            # save_model requires a path that does not exist yet.
            path = Path(scratch) / "model"
            module.save_model(
                **{FLAVOR_ARG[flavor]: model},
                **FLAVOR_KWARGS.get(flavor, {}),
                path=str(path),
                signature=infer_signature(input_example, predictions),
                input_example=input_example,
            )
            tracker.log_artifacts(path, "model")
        logger.info("Logged the mlflow.%s model under the run's model/", flavor)
    except Exception as e:
        logger.warning("MLflow model logging failed (%s); run artifacts unaffected", e)


def infer_signature(input_example, predictions):
    """Best-effort model signature; None when it cannot be inferred.

    A signature is documentation, not correctness: failing to derive one
    must not stop the model being logged.
    """
    if input_example is None:
        return None
    try:
        from mlflow.models import infer_signature as mlflow_infer_signature

        return mlflow_infer_signature(input_example, predictions)
    except Exception as e:
        logger.debug("Signature inference skipped (%s)", e)
        return None
