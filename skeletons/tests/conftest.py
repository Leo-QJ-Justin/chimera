"""Test constants derive from schema defaults, never from user config."""

import sys
from pathlib import Path

# Make `core` importable when pytest runs from the skeletons/ directory
# or the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import RunConfig, SplitConfig  # noqa: E402

TEST_SEED: int = RunConfig().seed
TEST_TRAIN_SIZE: float = SplitConfig().train_size
