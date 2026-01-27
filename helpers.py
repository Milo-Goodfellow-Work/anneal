#!/usr/bin/env python3
"""Anneal Helpers - Configuration and utilities."""
from __future__ import annotations
import os, re, time, tomllib, subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, NamedTuple

# ============================================================
# Configuration
# ============================================================

SECRETS_FILE = Path("secrets.toml")
SPEC_DIR = Path("spec").resolve()
SPEC_SRC_DIR = SPEC_DIR / "Spec"
SPEC_TESTS_DIR = SPEC_DIR / "tests"
SPEC_REPORTS_DIR = SPEC_DIR / "reports"

MODEL_ID = "gemini-3-flash-preview"
MAX_TOOL_READ_CHARS = 80_000
MAX_SESSION_TURNS = 16

DIFF_REQUIRED_RUNS = 5
DIFF_MIN_CASES_PER_RUN = 5
DIFF_SEED_START = 1
DIFF_MIN_OUTPUT_RATIO = 0.75

GEN_TIMEOUT_S = 8
C_RUN_TIMEOUT_S = 8
LEAN_RUN_TIMEOUT_S = 3000

LOCKED_LEAN_FILENAMES = {"Prelude.lean"}

PRELUDE_REQUIRED_IMPORTS = ["Std", "Std.Data.TreeMap", "Std.Data.TreeSet", 
                            "Std.Data.HashMap", "Std.Data.HashSet", "Mathlib"]

# ============================================================
# Utilities
# ============================================================

def log(msg: str) -> None:
    print(f"[Anneal] {msg}", flush=True)

def load_secrets() -> dict:
    if SECRETS_FILE.exists():
        with SECRETS_FILE.open("rb") as f:
            return tomllib.load(f)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        secrets = {"GEMINI_API_KEY": gemini_key}
        if k := os.environ.get("ARISTOTLE_API_KEY"):
            secrets["ARISTOTLE_API_KEY"] = k
        return {"secrets": secrets}
    raise FileNotFoundError(f"{SECRETS_FILE} not found and GEMINI_API_KEY not in env")

def list_project_files(base_dir: Path) -> List[str]:
    if not base_dir.exists(): return []
    files = []
    for root, dirs, fns in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for fn in fns:
            files.append(str((Path(root) / fn).relative_to(base_dir)).replace("\\", "/"))
    return sorted(files)

def list_lean_files(base_dir: Path) -> List[str]:
    return [f for f in list_project_files(base_dir) if f.endswith(".lean")]

def run_lake_build(cwd: Path) -> str:
    start = time.time()
    try:
        res = subprocess.run(["lake", "build"], cwd=str(cwd), capture_output=True, text=True, check=False)
        t = time.time() - start
        if res.returncode == 0:
            return f"Build Success ({t:.2f}s)"
        return f"Build Failed (exit={res.returncode}, {t:.2f}s):\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Error: {e}"

def run_lake_build_target(cwd: Path, target: Optional[str] = None) -> str:
    cmd = ["lake", "build"] + ([target] if target else [])
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        return "Build Success" if res.returncode == 0 else f"Build Failed:\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Error: {e}"

def module_name_from_lean_path(rel_path: str) -> Optional[str]:
    p = Path(rel_path)
    return "Spec." + ".".join(p.with_suffix("").parts) if p.suffix == ".lean" else None

# ============================================================
# Lean error parsing
# ============================================================

class LeanError(NamedTuple):
    file: str
    line: int
    col: int
    msg: str

LEAN_ERR_RE = re.compile(r"^error:\s+(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+(?P<msg>.*)$", re.MULTILINE)

def parse_lean_errors(output: str, max_n: int = 6) -> List[LeanError]:
    return [LeanError(m.group("file").strip(), int(m.group("line")), int(m.group("col")), m.group("msg").strip())
            for m in list(LEAN_ERR_RE.finditer(output))[:max_n]]

def excerpt_around(text: str, line: int, radius: int = 14) -> str:
    lines = text.splitlines()
    i = max(1, line) - 1
    return "\n".join(f"{'>> ' if idx == i else '   '}{idx+1:4d}: {lines[idx]}" 
                     for idx in range(max(0, i - radius), min(len(lines), i + radius + 1)))

# ============================================================
# Prelude
# ============================================================

PRELUDE_PATH = SPEC_SRC_DIR / "Prelude.lean"

def ensure_prelude_and_lockdown() -> None:
    SPEC_SRC_DIR.mkdir(parents=True, exist_ok=True)
    imports = "\n".join(f"import {m}" for m in PRELUDE_REQUIRED_IMPORTS)
    default = f"{imports}\n\nnamespace Spec\nabbrev U8 := UInt8\nabbrev U16 := UInt16\nabbrev U32 := UInt32\nabbrev U64 := UInt64\nend Spec\n"
    if not PRELUDE_PATH.exists():
        PRELUDE_PATH.write_text(default)

# ============================================================
# Tool schema
# ============================================================

def _tool(name: str, desc: str, props: Dict[str, Any], req: List[str]) -> Dict[str, Any]:
    return {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": req}}

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

def validate_basic_lean_shape(project: str, rel_path: str, content: str) -> tuple[bool, str]:
    if not content.strip():
        return False, "Empty file"
    if f"namespace Spec.{project}" not in content:
        return False, f"Missing namespace Spec.{project}"
    if f"end Spec.{project}" not in content:
        return False, f"Missing end Spec.{project}"
    if not rel_path.endswith("Verif.lean") and "sorry" in content:
        return False, "'sorry' not allowed outside Verif.lean"
    return True, ""
