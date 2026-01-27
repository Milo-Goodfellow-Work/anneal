"""Scaffold generation - copy templates and set up project structure."""
from __future__ import annotations
import shutil
from pathlib import Path
from helpers import log, SPEC_DIR, SPEC_SRC_DIR, SPEC_TESTS_DIR, SPEC_REPORTS_DIR

TEMPLATE_DIR = Path(__file__).parent.parent / "template"

def init_project(ctx: dict) -> None:
    """Copy template files and set up project structure."""
    # Copy entire template/spec to spec/ (skip existing files)
    for src in (TEMPLATE_DIR / "spec").rglob("*"):
        if src.is_file():
            rel = src.relative_to(TEMPLATE_DIR / "spec")
            dst = SPEC_DIR / rel
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    
    # Create directories
    SPEC_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ctx["source_root"].mkdir(parents=True, exist_ok=True)
    
    # Set up allowed writes
    ctx["allowed_lean_writes"] = {"Main.lean", "Verif.lean", "tests/Harness.lean"}
    for i in range(1, 6):
        ctx["allowed_lean_writes"].add(f"Module{i}.lean")
    ctx["allowed_text_writes"] = {"spec/tests/gen_inputs.py", "spec/tests/harness.c"}
    ctx["locked_lean_paths"] = {"Prelude.lean"}
