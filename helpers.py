#!/usr/bin/env python3
# Anneal Helpers - Shared configuration, filesystem utilities, and tool schemas.
"""Anneal Helpers - Configuration and utilities."""
from __future__ import annotations
import os, re, time, tomllib, subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, NamedTuple

# ============================================================
# Configuration
# ============================================================
# This section defines the directory structure and global constants.

# Local secrets file (not used in GCP mode).
SECRETS_FILE = Path("secrets.toml")
# Root of the Lean 4 project.
SPEC_DIR = Path("spec").resolve()
# Lean source code subdirectory.
SPEC_SRC_DIR = SPEC_DIR / "Src"
# Test artifacts and executable location.
SPEC_TESTS_DIR = SPEC_DIR / "tests"
# Persistent reports for verification tracking.
SPEC_REPORTS_DIR = SPEC_DIR / "reports"

# The specific Gemini model version used for generation.
MODEL_ID = "gemini-3-flash-preview"
# Threshold to prevent the LLM context from being overwhelmed by large files.
MAX_TOOL_READ_CHARS = 80_000
# Safety cap for agentic loops.
MAX_SESSION_TURNS = 16

# Parameters for Stage 1 differential testing.
DIFF_TOTAL_CASES = 25
DIFF_SEED_START = 1

# Timeouts for various subprocess executions.
GEN_TIMEOUT_S = 8
C_RUN_TIMEOUT_S = 8
LEAN_RUN_TIMEOUT_S = 3000

# Files that the agent is strictly prohibited from modifying.
LOCKED_LEAN_FILENAMES = {"Prelude.lean"}

# ============================================================
# Utilities
# ============================================================

def log(msg: str) -> None:
    # Standard logging with flush to ensure real-time visibility in Cloud Run.
    print(f"[Anneal] {msg}", flush=True)

def _read_text_file(path: Path) -> str:
    # Safe read helper.
    return path.read_text() if path.exists() else ""

def _write_text_file(path: Path, content: str) -> None:
    # Safe write helper: creates parent directories automatically.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

def is_writable(path: str) -> bool:
    """Check if a file path is writable by the model."""
    # This function enforces the sandbox rules for the LLM agent.
    # It prevents the model from overwriting core infrastructure (e.g. main.py).
    path = path.replace("\\", "/").lstrip("/").lstrip("./")
    
    # RULE: C code goes anywhere in generated/
    if path.startswith("generated/"):
        return True
    
    # RULE: Lean files in spec/Src/ (but not Prelude)
    if path.startswith("spec/Src/") or not "/" in path:  # relative lean paths
        if path.endswith("Prelude.lean") or path == "Prelude.lean":
            return False
        if path.endswith(".lean"):
            return True
    
    # RULE: Specific test harnesses allowed.
    if path in {"spec/tests/gen_inputs.py", "spec/tests/harness.c"}:
        return True
    
    return False

def list_project_files(base_dir: Path) -> List[str]:
    # Recursively list files, ignoring git and cache artifacts.
    if not base_dir.exists(): return []
    files = []
    for root, dirs, fns in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for fn in fns:
            files.append(str((Path(root) / fn).relative_to(base_dir)).replace("\\", "/"))
    return sorted(files)

def list_lean_files(base_dir: Path) -> List[str]:
    # Convenience filter for Lean source files.
    return [f for f in list_project_files(base_dir) if f.endswith(".lean")]

def run_lake_build(cwd: Path) -> str:
    # Execute the Lean build system (Lake) and capture results.
    start = time.time()
    try:
        # Run with verbose output to identify compilation bottlenecks.
        # DEBUG: Use -v to see what is slowing it down
        res = subprocess.run(["lake", "build", "-v"], cwd=str(cwd), capture_output=True, text=True, check=False)
        t = time.time() - start
        
        # Log detail for performance monitoring.
        # Log output regardless of success to debug slowness
        log(f"DEBUG LAKE BUILD ({t:.1f}s):\nSTDOUT HEAD:\n{res.stdout[:2000]}\nSTDERR:\n{res.stderr}")
        
        if res.returncode == 0:
            return f"Build Success ({t:.2f}s)"
        return f"Build Failed (exit={res.returncode}, {t:.2f}s):\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Error: {e}"

def run_lake_build_target(cwd: Path, target: Optional[str] = None) -> str:
    # Execute a specific Lake target (e.g. for individual test harnesses).
    cmd = ["lake", "build"] + ([target] if target else [])
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        return "Build Success" if res.returncode == 0 else f"Build Failed:\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Error: {e}"

def module_name_from_lean_path(rel_path: str) -> Optional[str]:
    # Convert a filesystem path to a Lean module name (e.g. Src/Main.lean -> Spec.Src.Main).
    p = Path(rel_path)
    return "Spec." + ".".join(p.with_suffix("").parts) if p.suffix == ".lean" else None

# ============================================================
# Lean error parsing
# ============================================================
# This section facilitates precise feedback to the LLM agent about build failures.

class LeanError(NamedTuple):
    file: str
    line: int
    col: int
    msg: str

# Regex to capture Lean 4 compiler diagnostics.
LEAN_ERR_RE = re.compile(r"^error:\s+(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+(?P<msg>.*)$", re.MULTILINE)

def parse_lean_errors(output: str, max_n: int = 6) -> List[LeanError]:
    # Extract the first N errors to present to the model.
    return [LeanError(m.group("file").strip(), int(m.group("line")), int(m.group("col")), m.group("msg").strip())
            for m in list(LEAN_ERR_RE.finditer(output))[:max_n]]

def excerpt_around(text: str, line: int, radius: int = 14) -> str:
    # Create a code snippet with line numbers around an error location.
    lines = text.splitlines()
    i = max(1, line) - 1
    return "\n".join(f"{'>> ' if idx == i else '   '}{idx+1:4d}: {lines[idx]}" 
                     for idx in range(max(0, i - radius), min(len(lines), i + radius + 1)))

# ============================================================
# Tool schema
# ============================================================
# This defines the "Function Calling" interface for the LLM agent.

def _tool(name: str, desc: str, props: Dict[str, Any], req: List[str]) -> Dict[str, Any]:
    # Helper to construct individual tool definitions.
    return {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": req}}

# The Master Schema: defines all capabilities available to the co-generation agent.
TOOLS_SCHEMA = [
    _tool("read_source_file", "Read source file from examples/<project>/", 
          {"path": {"type": "string"}}, ["path"]),
    _tool("read_lean_file", "Read Lean file from spec/Spec/", 
          {"path": {"type": "string"}}, ["path"]),
    _tool("write_lean_file", "Write Lean file under spec/Spec/", 
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _tool("write_text_file", "Write non-Lean file", 
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _tool("verify_build", "Run lake build", {}, []),
    _tool("restart_translation", "Restart translation (use only if fundamentally broken)", 
          {"reason": {"type": "string"}}, ["reason"]),
    _tool("run_differential_test", "Run differential tests between C and Lean", 
          {"gen_script_path": {"type": "string"}, "c_harness_path": {"type": "string"}, "lean_harness_path": {"type": "string"}}, 
          ["gen_script_path", "c_harness_path", "lean_harness_path"]),
    _tool("submit_stage", "Signal stage complete", {"summary": {"type": "string"}}, ["summary"]),
]

# ============================================================
# Validation (minimal)
# ============================================================

def validate_basic_lean_shape(rel_path: str, content: str) -> tuple[bool, str]:
    # Basic structural check to ensure Lean files are valid and don't use 'sorry'.
    if not content.strip():
        return False, "Empty file"
    if "namespace Src" not in content:
        return False, "Missing namespace Src"
    if "end Src" not in content:
        return False, "Missing end Src"
    # 'sorry' is only permitted in the Verif.lean file (which is populated by Aristotle).
    if not rel_path.endswith("Verif.lean") and "sorry" in content:
        return False, "'sorry' not allowed outside Verif.lean"
    return True, ""
