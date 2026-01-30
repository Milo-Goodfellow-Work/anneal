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
    test_data = _get_test_data(ctx)
    
    # Write test data JSON
    tests_path = SPEC_REPORTS_DIR / "tests.json"
    SPEC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tests_path.write_text(json.dumps(test_data, indent=2))
    log(f"Generated test data at {tests_path}")
    
    return str(tests_path)


def _extract_api_info(ctx: dict) -> Dict[str, Any]:
    """Extract functions and structs from C headers."""
    source_root = Path("generated")
    
    functions = []
    structs = []
    
    for header in sorted(source_root.glob("*.h")):
        content = _read_text_file(header)
        
        # Extract struct definitions
        # Match: typedef struct { ... } Name;
        struct_pattern = r'typedef\s+struct\s*\{([^}]*)\}\s*(\w+)\s*;'
        for match in re.finditer(struct_pattern, content, re.DOTALL):
            body = match.group(1).strip()
            name = match.group(2).strip()
            
            # Parse struct fields
            fields = []
            for line in body.split('\n'):
                line = line.strip().rstrip(';')
                if line and not line.startswith('//'):
                    fields.append(line)
            
            structs.append({
                "name": name,
                "fields": fields,
                "file": header.name,
            })
        
        # Extract function declarations
        # Match: type func(params);
        func_pattern = r'^\s*(\w[\w\s\*]+?)\s+(\w+)\s*\(([^)]*)\)\s*;'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            ret_type = match.group(1).strip()
            func_name = match.group(2).strip()
            params_str = match.group(3).strip()
            
            # Skip internal functions
            if func_name.startswith('_') or ret_type in ['typedef', '#define']:
                continue
            
            # Parse parameters
            params = []
            if params_str and params_str != 'void':
                for p in params_str.split(','):
                    p = p.strip()
                    if p:
                        params.append(p)
            
            functions.append({
                "name": func_name,
                "return": ret_type,
                "params": params,
                "file": header.name,
            })
    
    return {"functions": functions, "structs": structs}


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


# For backwards compatibility
def generate_equivalence_report(ctx: dict) -> str:
    """Alias for generate_report."""
    return generate_report(ctx)
