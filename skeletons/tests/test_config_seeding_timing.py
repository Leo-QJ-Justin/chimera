import logging

import numpy as np
import pytest
from pydantic import ValidationError

from core.config import (
    MlflowConfig,
    SplitConfig,
    log_config_defaults,
    to_plain_dict,
    warn_extra_sections,
)
from core.seeding import set_seed
from core.timing import stage_timer


def test_split_ratios_must_sum_to_one():
    with pytest.raises(ValidationError, match="sum to 1.0"):
        SplitConfig(train_size=0.8, val_size=0.15, test_size=0.15)


def test_mlflow_disabled_by_schema_default():
    assert MlflowConfig().enabled is False


def test_log_config_defaults_warns_only_on_unset(caplog):
    with caplog.at_level(logging.WARNING, logger="core.config"):
        log_config_defaults(SplitConfig(train_size=0.7, val_size=0.2, test_size=0.1))
    assert "seed" in caplog.text
    assert "train_size" not in caplog.text


def test_log_config_defaults_quiet_when_disabled(caplog):
    with caplog.at_level(logging.WARNING, logger="core.config"):
        log_config_defaults(MlflowConfig())
    assert caplog.text == ""


def test_warn_extra_sections(caplog):
    with caplog.at_level(logging.WARNING, logger="core.config"):
        warn_extra_sections(SplitConfig, {"mode": "shuffle", "surprise": 1})
    assert "surprise" in caplog.text


def test_to_plain_dict_passthrough():
    assert to_plain_dict({"a": 1}) == {"a": 1}


def test_set_seed_reproducible_numpy():
    set_seed(123)
    a = np.random.rand(3)
    set_seed(123)
    b = np.random.rand(3)
    assert np.allclose(a, b)
    assert set_seed(7) == 7


def test_stage_timer_logs_and_tracks():
    class FakeTracker:
        def __init__(self):
            self.calls = []

        def log_metrics(self, metrics, step=None):
            self.calls.append((metrics, step))

    tracker = FakeTracker()
    with stage_timer("clean", tracker=tracker, step=3):
        pass
    (metrics, step), = tracker.calls
    assert "time_clean_s" in metrics and step == 3
