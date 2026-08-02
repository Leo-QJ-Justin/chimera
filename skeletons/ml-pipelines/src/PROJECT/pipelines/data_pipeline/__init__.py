"""Data pipeline: raw -> clean -> stateless features -> model-input table.

The package exports what a caller outside the pipeline needs: the
orchestrator, and ``load_manifest`` so a later stage can read what a data
run produced without knowing where the writer lives. Everything else is
imported from the module that defines it, so the import says where the
code is.
"""

from .classes.dataset_writer import load_manifest
from .pipeline import DataPipeline

__all__ = ["DataPipeline", "load_manifest"]
