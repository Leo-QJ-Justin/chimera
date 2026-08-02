"""Stage timing as a permanent part of a run's output.

A context manager that logs wall time for a named stage and, when a
tracker is passed, records it as a metric. It replaces ad hoc
``time.time()`` stopwatch pairs, so timings survive past debugging.
"""

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def stage_timer(name: str, tracker=None, step: int | None = None):
    """Time a pipeline stage.

    Args:
        name: Stage label; becomes metric ``time_<name>_s``.
        tracker: Optional ``core.tracking.Tracker``; timing is logged as
            a metric when provided.
        step: Optional step (e.g. epoch) for per-iteration timings.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info("Stage %s took %.2fs", name, elapsed)
        if tracker is not None:
            tracker.log_metrics({f"time_{name}_s": elapsed}, step=step)
