"""Project package.

Renamed wholesale by the scaffold; every import *inside* this package is
relative (``from ..core import ...``) so the rename touches only the
directory name and the literal ``PROJECT`` in run_*.py, tests/,
pyproject.toml.
"""

__version__ = "0.1.0"
