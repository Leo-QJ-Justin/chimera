"""Stateless internals of the training pipeline.

``preprocessing`` and ``splitting`` serve every trainer. The remaining
modules (``loops``, ``callbacks``, ``checkpointing``, ``device``,
``sanity``, ``datasets``, ``architectures``) are ``TorchTrainer``'s
internals and import torch, so they are not re-exported here: importing
this package must not require the torch extra.
"""

from .preprocessing import build_preprocessor
from .splitting import (
    make_cv_splitter,
    record_splits,
    resolve_feature_columns,
    split_frame,
)

__all__ = [
    "build_preprocessor",
    "make_cv_splitter",
    "record_splits",
    "resolve_feature_columns",
    "split_frame",
]
