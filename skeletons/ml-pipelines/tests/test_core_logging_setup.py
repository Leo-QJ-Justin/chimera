"""Logging setup: the programmatic and YAML paths, and their failure modes."""

import logging

from PROJECT.core.logging_setup import configure_logging


def test_programmatic_mode_returns_log_path(tmp_path):
    path = configure_logging(package="skel_test_pkg", log_dir=tmp_path, log_prefix="unit")
    logger = logging.getLogger("skel_test_pkg.sub")
    logger.info("hello file")
    assert path is not None and path.exists()
    assert "hello file" in path.read_text()


def test_reconfigure_is_idempotent(tmp_path):
    configure_logging(package="skel_test_pkg2", log_dir=tmp_path)
    configure_logging(package="skel_test_pkg2", log_dir=tmp_path)
    assert len(logging.getLogger("skel_test_pkg2").handlers) == 2  # console+file


def test_console_only_returns_none():
    assert configure_logging(package="skel_test_pkg3") is None


def test_yaml_mode_rebinds_log_dir(tmp_path):
    config = tmp_path / "logging.yaml"
    config.write_text(
        """
version: 1
disable_existing_loggers: false
formatters:
  plain: {format: "%(levelname)s %(message)s"}
handlers:
  file:
    class: logging.FileHandler
    filename: somewhere/else/app.log
    formatter: plain
root: {level: INFO, handlers: [file]}
"""
    )
    log_dir = tmp_path / "logs"
    path = configure_logging(config_path=config, log_dir=log_dir)
    assert path == log_dir / "app.log"
    logging.getLogger("anything").info("rebound")
    assert "rebound" in path.read_text()


def test_broken_yaml_degrades_not_dies(tmp_path, caplog):
    missing = tmp_path / "nope.yaml"
    assert configure_logging(config_path=missing) is None
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\nhandlers: {h: {class: not.a.Class}}\nroot: {handlers: [h]}"
    )
    assert configure_logging(config_path=bad) is None
