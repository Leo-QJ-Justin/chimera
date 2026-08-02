"""Config validation layer: pydantic on top of Hydra composition.

Hydra owns file composition, config groups, CLI overrides, and sweeps.
This module owns what runs after composition: shared base models that
pipeline schemas subclass, cross-field validation, and defaults
transparency - every value the run did not set explicitly is warned
about, so an unexpected value can be traced back to its default.

Composite schemas use ``extra="ignore"`` because composition injects
sections a given pipeline does not use; ``warn_extra_sections`` surfaces
them without failing.
"""

import logging
import math
from typing import Literal

from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)


# ------------------------------------------------------------ base models


class LoggingConfig(BaseModel):
    """Console and file logging settings for a run."""

    model_config = {"extra": "ignore"}

    level: str = "INFO"
    log_to_file: bool = True
    log_dir: str = "logs"
    log_prefix: str = "run"
    timezone: str = "Asia/Singapore"


class MlflowConfig(BaseModel):
    """Experiment tracking settings consumed by ``init_tracking``."""

    model_config = {"extra": "ignore"}

    # Schema default is off so tests and minimal configs are predictable;
    # projects turn it on in their base config.
    enabled: bool = False
    tracking_uri: str = "sqlite:///mlflow.db"
    experiment_name: str = "default"
    run_name: str | None = None


class SplitConfig(BaseModel):
    """Split mode, proportions, keys and seed for a run."""

    model_config = {"extra": "ignore"}

    mode: Literal["shuffle", "stratified", "temporal", "group"] = "stratified"
    train_size: float = 0.7
    val_size: float = 0.15
    test_size: float = 0.15
    key_cols: list[str] = []
    # temporal mode: boundary dates declared, membership still recorded
    boundaries: dict[str, str] = {}
    seed: int = 42

    @model_validator(mode="after")
    def validate_ratios(self):
        """Require the three split sizes to sum to 1.0."""
        total = self.train_size + self.val_size + self.test_size
        if not math.isclose(total, 1.0, rel_tol=1e-9):
            raise ValueError(f"train/val/test sizes must sum to 1.0, got {total}")
        return self


class RunConfig(BaseModel):
    """The one seed source plus run-level knobs."""

    model_config = {"extra": "ignore"}

    seed: int = 42
    output_dir: str = "outputs"
    timezone: str = "Asia/Singapore"


# --------------------------------------------------------------- helpers


def to_plain_dict(cfg) -> dict:
    """Coerce an OmegaConf/Hydra config (or a dict) to a plain dict."""
    try:
        from omegaconf import OmegaConf

        if OmegaConf.is_config(cfg):
            return OmegaConf.to_container(cfg, resolve=True)
    except ImportError:
        pass
    return dict(cfg)


def log_config_defaults(model: BaseModel, prefix: str = "") -> None:
    """Warn about every leaf value the user did not explicitly set.

    Recurses into nested models; sections carrying ``enabled=False`` stay
    quiet. Uses ``model_fields_set`` so only true defaults are reported.
    """
    if getattr(model, "enabled", True) is False:
        return
    defaulted = set(type(model).model_fields) - model.model_fields_set
    leaf_defaults = {
        f: getattr(model, f)
        for f in sorted(defaulted)
        if not isinstance(getattr(model, f), BaseModel)
    }
    if leaf_defaults:
        logger.warning(
            "Config section %s using defaults for: %s",
            prefix or type(model).__name__,
            leaf_defaults,
        )
    for field in type(model).model_fields:
        value = getattr(model, field)
        if isinstance(value, BaseModel):
            log_config_defaults(value, prefix=f"{prefix}{field}.")


def warn_extra_sections(schema_cls: type[BaseModel], raw: dict) -> None:
    """Surface top-level keys the schema will ignore, without failing."""
    extras = set(raw) - set(schema_cls.model_fields)
    if extras:
        logger.warning(
            "Config has sections not used by %s: %s",
            schema_cls.__name__,
            sorted(extras),
        )
