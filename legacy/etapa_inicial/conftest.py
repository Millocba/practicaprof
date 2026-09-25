"""Hace importables `synthetic_data` y `raw_sources` desde su ubicación en legacy/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
