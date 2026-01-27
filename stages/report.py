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
    log, _read_text_file, _write_text_file, SPEC_REPORTS_DIR,
    DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN,
)


def generate_report(ctx: dict) -> str:
    """Generate unified report and test data files."""
    project_name = ctx["name"]
    
    # Get test results from context
    equiv_state = ctx.get("equiv_state", {})
    last_report = equiv_state.get("last_report", {})
    
    # Extract API info from headers (functions + structs)
    api_info = _extract_api_info(ctx)
    
    # Get test data
    test_data = _get_test_data(ctx)
    
    # Write test data JSON
    tests_path = SPEC_REPORTS_DIR / f"{project_name}_tests.json"
    _write_text_file(tests_path, json.dumps(test_data, indent=2))
    log(f"Generated test data at {tests_path}")
    
    # Build and write unified report
    report_path = SPEC_REPORTS_DIR / f"{project_name}_report.md"
    report_content = _build_unified_report(ctx, api_info, test_data, last_report)
    _write_text_file(report_path, report_content)
    log(f"Generated report at {report_path}")
    
    return str(report_path)


def _extract_api_info(ctx: dict) -> Dict[str, Any]:
    """Extract functions and structs from C headers."""
    source_root = ctx.get("source_root", Path("generated/generated"))
    if isinstance(source_root, str):
        source_root = Path(source_root)
    
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
    equiv_state = ctx.get("equiv_state", {})
    return equiv_state.get("test_data", {
        "seeds": [],
        "total_cases": 0,
        "all_pass": False,
    })


def _build_unified_report(
    ctx: dict,
    api_info: Dict[str, Any],
    test_data: Dict[str, Any],
    summary: Dict[str, Any],
) -> str:
    """Build the unified report markdown."""
    project_name = ctx["name"]
    
    passed = summary.get("passed_runs", 0) if isinstance(summary, dict) else 0
    required = summary.get("required_runs", DIFF_REQUIRED_RUNS) if isinstance(summary, dict) else DIFF_REQUIRED_RUNS
    total_time = summary.get("total_time_s", 0) if isinstance(summary, dict) else 0
    
    # Check for formal proofs
    verif_path = ctx.get("spec_src_root", Path("spec/Spec")) / f"{project_name}/Verif.lean"
    has_proofs = verif_path.exists() and "sorry" not in _read_text_file(verif_path)
    
    status = "✅ VERIFIED" if passed >= required else "❌ FAILED"
    
    report = f"""# {project_name} — Verification Report

**Status:** {status}  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## Summary

| Metric | Value |
|--------|-------|
| Differential Tests | {passed}/{required} seeds passed |
| Total Test Time | {total_time:.1f}s |
| Formal Proofs | {"✅ Complete" if has_proofs else "⏳ Pending"} |

---

## API

"""
    
    # List structs first (if any function returns a custom type)
    structs = api_info.get("structs", [])
    functions = api_info.get("functions", [])
    
    # Find which structs are used as return types
    return_types = {f["return"] for f in functions}
    relevant_structs = [s for s in structs if s["name"] in return_types]
    
    for sig in functions:
        report += f"### `{sig['name']}`\n\n"
        report += f"**Returns:** `{sig['return']}`\n\n"
        
        if sig['params']:
            report += "**Parameters:**\n"
            for p in sig['params']:
                report += f"- `{p}`\n"
        else:
            report += "**Parameters:** none\n"
        
        # If return type is a struct, show its definition
        matching_struct = next((s for s in structs if s["name"] == sig["return"]), None)
        if matching_struct:
            report += f"\n**Return Type Definition:**\n```c\ntypedef struct {{\n"
            for field in matching_struct["fields"]:
                report += f"    {field};\n"
            report += f"}} {matching_struct['name']};\n```\n"
        
        report += "\n"
    
    if not functions:
        report += "*No function signatures extracted*\n\n"
    
    # Test results
    report += "---\n\n## Test Results\n\n"
    
    seeds = test_data.get("seeds", [])
    if seeds:
        for seed_data in seeds:
            seed = seed_data.get("seed", "?")
            cases = seed_data.get("cases", [])
            all_pass = all(c.get("match", False) for c in cases)
            
            report += f"### Seed {seed} {'✅' if all_pass else '❌'}\n\n"
            report += "| # | C Output | Lean Output | Match |\n"
            report += "|---|----------|-------------|-------|\n"
            
            for i, case in enumerate(cases, 1):
                c_out = case.get("c", "-")
                lean_out = case.get("lean", "-")
                match = "✓" if case.get("match", False) else "✗"
                report += f"| {i} | `{c_out}` | `{lean_out}` | {match} |\n"
            
            report += "\n"
    else:
        report += "*No test data recorded*\n"
    
    report += "---\n\n*Generated by Anneal Verification Agent*\n"
    
    return report


# For backwards compatibility
def generate_equivalence_report(ctx: dict) -> str:
    """Alias for generate_report."""
    return generate_report(ctx)
