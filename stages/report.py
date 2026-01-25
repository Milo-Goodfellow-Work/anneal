"""
Anneal - Minimal Equivalence Report Generator.

Generates a concise report with:
1. Function signatures (inputs/outputs with types)
2. Every test case I/O pair
"""
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

from helpers import (
    log, _read_text_file, _write_text_file, SPEC_REPORTS_DIR, SPEC_TESTS_DIR,
)


def generate_equivalence_report(ctx: dict) -> str:
    """Generate minimal equivalence report."""
    project_name = ctx["name"]
    report_path = SPEC_REPORTS_DIR / f"{project_name}_EquivalenceReport.md"
    
    equiv_state = ctx.get("equiv_state", {})
    last_report = equiv_state.get("last_report", {})
    
    # Extract function signatures from headers
    signatures = _extract_signatures(ctx)
    
    # Parse test traces
    trace_data = _parse_trace_file(project_name)
    
    # Build minimal report
    content = _build_report(project_name, signatures, trace_data, last_report)
    
    _write_text_file(report_path, content)
    log(f"Generated equivalence report at {report_path}")
    return str(report_path)


def _extract_signatures(ctx: dict) -> List[Dict[str, Any]]:
    """Extract function signatures from C headers."""
    source_root = ctx.get("source_root", Path("generated/generated"))
    if isinstance(source_root, str):
        source_root = Path(source_root)
    
    signatures = []
    
    for header in sorted(source_root.glob("*.h")):
        content = _read_text_file(header)
        
        # Find function declarations (simple pattern)
        # Matches: type func(params);
        pattern = r'^\s*(\w[\w\s\*]+?)\s+(\w+)\s*\(([^)]*)\)\s*;'
        
        for match in re.finditer(pattern, content, re.MULTILINE):
            ret_type = match.group(1).strip()
            func_name = match.group(2).strip()
            params_str = match.group(3).strip()
            
            # Skip if it looks like a typedef or macro
            if func_name.startswith('_') or ret_type in ['typedef', '#define']:
                continue
            
            # Parse parameters
            params = []
            if params_str and params_str != 'void':
                for p in params_str.split(','):
                    p = p.strip()
                    if p:
                        params.append(p)
            
            signatures.append({
                "file": header.name,
                "name": func_name,
                "return": ret_type,
                "params": params,
            })
    
    return signatures


def _parse_trace_file(project_name: str) -> List[Dict[str, Any]]:
    """Parse trace file into test cases."""
    trace_path = SPEC_REPORTS_DIR / f"{project_name}_diff_trace.txt"
    if not trace_path.exists():
        return []
    
    content = _read_text_file(trace_path)
    test_cases = []
    case_num = 0
    current_seed = 0
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Parse seed header
        if line.startswith('# Seed'):
            try:
                parts = line.split()
                current_seed = int(parts[2])
            except:
                pass
            continue
        
        # Parse test case line: ✓ | input | C: output | Lean: output
        if line.startswith('✓') or line.startswith('✗'):
            case_num += 1
            match = line.startswith('✓')
            
            # Split by |
            parts = line.split('|')
            if len(parts) >= 4:
                inp = parts[1].strip()
                c_out = parts[2].replace('C:', '').strip()
                lean_out = parts[3].replace('Lean:', '').strip()
                
                test_cases.append({
                    "num": case_num,
                    "seed": current_seed,
                    "input": inp,
                    "c_output": c_out,
                    "lean_output": lean_out,
                    "match": match,
                })
    
    return test_cases


def _build_report(
    project_name: str,
    signatures: List[Dict[str, Any]],
    test_cases: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> str:
    """Build minimal report."""
    
    passed = summary.get("passed_runs", 0) if isinstance(summary, dict) else 0
    required = summary.get("required_runs", 5) if isinstance(summary, dict) else 5
    
    report = f"""# {project_name} — Equivalence Report

**Status:** {"✅ PASS" if passed >= required else "❌ FAIL"} ({passed}/{required} runs)  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## Functions

"""
    
    # List function signatures
    for sig in signatures:
        report += f"### `{sig['name']}`\n\n"
        report += f"**Returns:** `{sig['return']}`\n\n"
        
        if sig['params']:
            report += "**Parameters:**\n"
            for p in sig['params']:
                report += f"- `{p}`\n"
        else:
            report += "**Parameters:** none\n"
        
        report += "\n"
    
    if not signatures:
        report += "*No function signatures extracted*\n\n"
    
    # Test cases with explanations
    report += "---\n\n## Test Cases\n\n"
    
    if test_cases:
        for tc in test_cases:
            match_icon = "✅" if tc['match'] else "❌"
            report += f"### Test {tc['num']} {match_icon}\n\n"
            
            # Explain the input
            inp = tc['input']
            explanation = _explain_test_case(inp, tc['c_output'])
            
            report += f"**Input:** `{inp[:80]}{'...' if len(inp) > 80 else ''}`\n\n"
            report += f"{explanation}\n\n"
            
            report += f"**C Output:** `{tc['c_output']}`  \n"
            report += f"**Lean Output:** `{tc['lean_output']}`\n\n"
            
            if tc['match']:
                report += "> Both implementations produced the same answer.\n\n"
            else:
                report += "> ⚠️ **MISMATCH** — The implementations disagree!\n\n"
    else:
        report += "*No test cases recorded*\n"
    
    return report


def _explain_test_case(input_str: str, output_str: str) -> str:
    """Generate a plain-English explanation of what a test case means."""
    parts = input_str.split()
    
    if len(parts) < 2:
        return "> Could not parse input format."
    
    try:
        n = int(parts[0])
        target = int(parts[1])
        nums = [int(x) for x in parts[2:n+2]] if len(parts) > 2 else []
        
        # Build explanation
        explanation = f"> **Input:** {n} numbers"
        if n <= 10:
            explanation += f": [{', '.join(str(x) for x in nums)}]"
        explanation += "\n"
        explanation += f"> **Query:** Two numbers summing to {target}\n"
        
        # Explain the output
        if "Found:" in output_str:
            idx_parts = output_str.replace("Found:", "").strip().split()
            if len(idx_parts) >= 2:
                i1, i2 = int(idx_parts[0]), int(idx_parts[1])
                if i1 < len(nums) and i2 < len(nums):
                    v1, v2 = nums[i1], nums[i2]
                    explanation += f"> **Answer:** Positions {i1} and {i2} contain {v1} and {v2}, which sum to {v1 + v2}"
                else:
                    explanation += f"> **Answer:** Found indices {i1} and {i2}"
        elif "Not Found" in output_str or "Not found" in output_str:
            explanation += "> **Answer:** No such pair exists"
        
        return explanation
    except:
        return "> Could not parse test case."

