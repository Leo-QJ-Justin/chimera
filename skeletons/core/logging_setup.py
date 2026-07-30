"""Logging bootstrap: configured once at the entry point, never at import.

Rules enforced by convention (see the skeleton READMEs):
- every module does ``logger = logging.getLogger(__name__)``;
- pure helper modules never log;
- scalars go through the logger, pre-formatted multi-line blocks through
  ``print`` (a level prefix would mangle them);
- the returned log-file path is uploaded as a run artifact by the caller.

Two modes:
- programmatic (default): package logger, tz-aware formatter, optional
  timestamped file handler;
- YAML dictConfig (production tier): pass ``config_path``; handler
  filenames are rebound into ``log_dir`` at load time and a broken config
  degrades to ``basicConfig`` rather than dying.
"""

import logging
import logging.config
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class TimezoneFormatter(logging.Formatter):
    """Format record timestamps in an explicit timezone."""

    def __init__(self, fmt: str, tz: str):
        super().__init__(fmt)
        self._tz = ZoneInfo(tz)

    def formatTime(self, record, datefmt=None):  # noqa: N802 (stdlib API)
        dt = datetime.fromtimestamp(record.created, tz=self._tz)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")


def configure_logging(
    package: str = "src",
    level: int = logging.INFO,
    log_dir: str | Path | None = None,
    log_prefix: str = "run",
    tz: str = "Asia/Singapore",
    config_path: str | Path | None = None,
) -> Path | None:
    """Configure logging once; idempotent on re-call.

    Returns:
        The log file path when file logging is active (log it as a run
        artifact), else None.
    """
    if config_path is not None:
        return _configure_from_yaml(config_path, log_dir, level)

    pkg_logger = logging.getLogger(package)
    pkg_logger.handlers.clear()
    pkg_logger.setLevel(level)
    pkg_logger.propagate = False

    formatter = TimezoneFormatter(_FORMAT, tz)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    pkg_logger.addHandler(console)

    if log_dir is None:
        return None
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo(tz)).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{log_prefix}_{stamp}.log"
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    pkg_logger.addHandler(file_handler)
    return log_path


def _configure_from_yaml(
    config_path: str | Path, log_dir: str | Path | None, fallback_level: int
) -> Path | None:
    """dictConfig with log-dir rebinding; degrades to basicConfig."""
    logger = logging.getLogger(__name__)
    try:
        import yaml

        with open(config_path) as f:
            log_config = yaml.safe_load(f)
        first_file = None
        if log_dir is not None:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            for handler in log_config.get("handlers", {}).values():
                if "filename" in handler:
                    rebound = log_dir / Path(handler["filename"]).name
                    handler["filename"] = str(rebound)
                    first_file = first_file or rebound
        logging.config.dictConfig(log_config)
        return first_file
    except FileNotFoundError:
        logging.basicConfig(format=_FORMAT, level=fallback_level)
        logger.error(
            "Logging config %s not found; basic config in use", config_path
        )
    except Exception as e:
        logging.basicConfig(format=_FORMAT, level=fallback_level)
        logger.error(
            "Logging config %s invalid (%s); basic config in use", config_path, e
        )
    return None
