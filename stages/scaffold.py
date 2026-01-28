"""Scaffold generation - set up project structure."""
from __future__ import annotations
from pathlib import Path
from helpers import SPEC_TESTS_DIR, SPEC_REPORTS_DIR

def init_project(ctx: dict) -> None:
    """Create required directories. Templates are copied by main.py at startup."""
    SPEC_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    Path("generated").mkdir(parents=True, exist_ok=True)
