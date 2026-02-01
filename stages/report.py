"""
Anneal - Unified Report Generator.

Generates two files:
1. <project>_tests.json - All test data (seeds, cases, I/O pairs)
2. <project>_report.md - Unified report with functions, structs, and test results
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from helpers import (
    log, _read_text_file, _write_text_file, SPEC_REPORTS_DIR, SPEC_SRC_DIR,
)


def generate_report(ctx: dict) -> str:
    """Generate test data file."""
    
    # Get test results from context
    equiv_state = ctx["equiv_state"]
    
    # Get test data
    # This data comes from 'equiv_state', which was populated by 
    # run_differential_test() in diff_test.py.
    # It contains seeds, inputs, outputs, and pass/fail status for every case.
    test_data = _get_test_data(ctx)
    
    # Write test data JSON
    tests_path = SPEC_REPORTS_DIR / "tests.json"
    SPEC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tests_path.write_text(json.dumps(test_data, indent=2))
    log(f"Generated test data at {tests_path}")
    
    return str(tests_path)


def _get_test_data(ctx: dict) -> Dict[str, Any]:
    """Get test data from context (stored by diff_test)."""
    equiv_state = ctx["equiv_state"]
    data = equiv_state.get("test_data", {
        "cases": [],
        "total_cases": 0,
        "all_pass": False,
    })
    # Include comment from submit_stage summary
    data["comment"] = equiv_state.get("submit_summary", "")
    return data



