#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import asyncio
import sys
import time
import tomllib
import json
import shutil
import re
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any
from dataclasses import dataclass

from openai import OpenAI

try:
    import aristotlelib
except ImportError:
    aristotlelib = None

# ---------------- Configuration ----------------
SECRETS_FILE = Path("secrets.toml")
SPEC_DIR = Path("spec")
SPEC_SRC_DIR = SPEC_DIR / "Spec"
EXAMPLES_DIR = Path("examples")

MODEL_ID = "gpt-5.2"
PRINT_TRUNC = 4000

# Safety limits (avoid accidentally stuffing the model context with huge blobs)
MAX_TOOL_READ_CHARS = 80_000
MAX_REPAIR_TURNS = 30

# ---------------- Utilities ----------------
def log(msg: str) -> None:
    print(f"[Anneal] {msg}", flush=True)

def trunc(s: str, n: int = PRINT_TRUNC) -> str:
    if s is None:
        return ""
    return s if len(s) <= n else (s[:n] + f"\n... (truncated, total {len(s)} chars)")

def load_secrets() -> dict:
    if not SECRETS_FILE.exists():
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            aristotle_key = os.environ.get("ARISTOTLE_API_KEY")
            secrets = {"OPENAI_API_KEY": key}
            if aristotle_key:
                secrets["ARISTOTLE_API_KEY"] = aristotle_key
            return {"secrets": secrets}
        raise FileNotFoundError(f"{SECRETS_FILE} not found and OPENAI_API_KEY not in env.")
    with SECRETS_FILE.open("rb") as f:
        return tomllib.load(f)

def list_project_files(base_dir: Path) -> List[str]:
    files: List[str] = []
    if not base_dir.exists():
        return files
    for root, dirs, filenames in os.walk(base_dir):
        if ".git" in dirs:
            dirs.remove(".git")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        for fn in filenames:
            abs_p = Path(root) / fn
            rel_p = abs_p.relative_to(base_dir)
            files.append(str(rel_p))
    return sorted(files)

def list_lean_files(base_dir: Path) -> List[str]:
    files: List[str] = []
    if not base_dir.exists():
        return files
    for root, dirs, filenames in os.walk(base_dir):
        if ".git" in dirs:
            dirs.remove(".git")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        for fn in filenames:
            if fn.endswith(".lean"):
                abs_p = Path(root) / fn
                rel_p = abs_p.relative_to(base_dir)
                files.append(str(rel_p))
    return sorted(files)

def run_lake_build(cwd: Path) -> str:
    start = time.time()
    try:
        res = subprocess.run(
            ["lake", "build"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        elapsed = time.time() - start
        if res.returncode == 0:
            return f"Build Success ({elapsed:.2f}s)"
        return f"Build Failed (exit={res.returncode}, {elapsed:.2f}s):\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Error running lake build: {e}"

def _safe_relpath(p: str) -> str:
    p = p.replace("\\", "/").lstrip("/")
    if p == "" or p == ".":
        raise ValueError("Empty path")
    # Prevent traversal
    parts = [x for x in p.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        raise ValueError(f"Path traversal not allowed: {p}")
    return "/".join(parts)

def _read_text_file(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def _write_text_file(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def _slug_to_camel(s: str) -> str:
    # Turn "order_engine" or "src/engine" into "OrderEngine" / "SrcEngine"
    parts = re.split(r"[^A-Za-z0-9]+", s)
    parts = [x for x in parts if x]
    if not parts:
        return "X"
    out = "".join(x[:1].upper() + x[1:] for x in parts)
    if out and out[0].isdigit():
        out = "X" + out
    return out

def _lean_out_path_for_source(project: str, src_rel: str, used: Dict[str, int]) -> str:
    src = Path(src_rel)
    stem = src.stem
    parent = str(src.parent).replace("\\", "/")
    if parent in (".", ""):
        base = _slug_to_camel(stem)
    else:
        base = _slug_to_camel(parent.replace("/", "_") + "_" + stem)
    name = base
    if name in used:
        used[name] += 1
        name = f"{name}{used[name]}"
    else:
        used[name] = 1
    return f"{project}/{name}.lean"

def _is_source_file(rel: str) -> bool:
    ext = Path(rel).suffix.lower()
    return ext in {".c", ".h", ".cc", ".cpp", ".hpp"}

# ---------------- Tool Schema ----------------
def _tool(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }

TOOLS_SCHEMA = [
    _tool(
        "read_source_file",
        "Read content of a source file from the example project (relative to examples/<project>/).",
        {"path": {"type": "string", "description": "Relative path in the example project"}},
        ["path"],
    ),
    _tool(
        "read_lean_file",
        "Read content of a Lean file from the Spec project (relative to spec/Spec/).",
        {"path": {"type": "string", "description": "Relative path in spec/Spec/ (e.g., 'order_engine/Engine.lean')"}},
        ["path"],
    ),
    _tool(
        "write_lean_file",
        "Write or overwrite a Lean file in the Spec project (relative to spec/Spec/).",
        {
            "path": {"type": "string", "description": "Relative path in spec/Spec/ (e.g., 'order_engine/Engine.lean')"},
            "content": {"type": "string", "description": "Full content of the file"},
        },
        ["path", "content"],
    ),
    _tool(
        "verify_build",
        "Run `lake build` in the spec/ directory to verify the Lean project builds.",
        {},
        [],
    ),
    _tool(
        "submit_stage",
        "Signal that the current stage is complete (only call this after the stage artifacts exist and build passes).",
        {"summary": {"type": "string", "description": "Brief summary of work done"}},
        ["summary"],
    ),
]

# ---------------- New Helpers for Targeted Repair ----------------

LEAN_ERR_RE = re.compile(
    r"^error:\s+(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+(?P<msg>.*)$",
    re.MULTILINE
)

@dataclass
class LeanError:
    file: str
    line: int
    col: int
    msg: str

def parse_lean_errors(build_output: str, *, max_n: int = 5) -> list[LeanError]:
    errs: list[LeanError] = []
    for m in LEAN_ERR_RE.finditer(build_output):
        errs.append(LeanError(
            file=m.group("file").strip(),
            line=int(m.group("line")),
            col=int(m.group("col")),
            msg=m.group("msg").strip(),
        ))
        if len(errs) >= max_n:
            break
    return errs

def excerpt_around(text: str, line_1based: int, *, radius: int = 12) -> str:
    lines = text.splitlines()
    i = max(1, line_1based) - 1
    lo = max(0, i - radius)
    hi = min(len(lines), i + radius + 1)
    out = []
    for idx in range(lo, hi):
        prefix = ">>" if idx == i else "  "
        out.append(f"{prefix} {idx+1:4d}: {lines[idx]}")
    return "\n".join(out)

# Prelude and Import Policy
PRELUDE_PATH = SPEC_SRC_DIR / "Prelude.lean"

def ensure_prelude() -> None:
    """
    Centralize imports so the model doesn't guess non-existent modules.
    """
    if PRELUDE_PATH.exists():
        return
    content = (
        "import Std\n\n"
        "namespace Spec\n\n"
        "-- Put shared defs/abbrevs here to avoid guessing Std module names.\n"
        "abbrev U8  := UInt8\n"
        "abbrev U16 := UInt16\n"
        "abbrev U32 := UInt32\n"
        "abbrev U64 := UInt64\n\n"
        "end Spec\n"
    )
    _write_text_file(PRELUDE_PATH, content)
    log(f"Wrote {PRELUDE_PATH}")

ALLOWED_IMPORT_PREFIXES = ["Std", "Spec", "Mathlib"]
STRICT_ALLOWED_IMPORTS = {"Spec.Prelude", "Std"}

IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_.]+)\s*$", re.MULTILINE)

def validate_imports(content: str, *, strict: bool = True) -> tuple[bool, list[str]]:
    mods = IMPORT_RE.findall(content)
    bad: list[str] = []
    for mod in mods:
        if strict:
            if mod not in STRICT_ALLOWED_IMPORTS and not mod.startswith("Spec."):
                bad.append(mod)
        else:
            if not any(mod == p or mod.startswith(p + ".") for p in ALLOWED_IMPORT_PREFIXES):
                bad.append(mod)
    return (len(bad) == 0, bad)

def run_lake_build_target(cwd: Path, target: str | None = None) -> str:
    start = time.time()
    cmd = ["lake", "build"]
    if target:
        cmd.append(target)
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        elapsed = time.time() - start
        if res.returncode == 0:
            return f"Build Success ({elapsed:.2f}s)"
        return f"Build Failed (exit={res.returncode}, {elapsed:.2f}s):\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Error running lake build: {e}"

def module_name_from_lean_path(rel_path_under_spec: str) -> str | None:
    p = Path(rel_path_under_spec)
    if p.suffix != ".lean":
        return None
    return "Spec." + ".".join(p.with_suffix("").parts)

# ---------------- Processor ----------------
class ProjectProcessor:
    def __init__(self, example_name: str, example_path: Path, client: OpenAI, secrets: dict):
        self.name = example_name
        self.source_root = example_path
        self.spec_pkg_root = SPEC_DIR
        self.spec_src_root = SPEC_SRC_DIR
        self.spec_project_root = self.spec_src_root / example_name  # spec/Spec/<project>/
        self.client = client
        self.secrets = secrets

        self.spec_project_root.mkdir(parents=True, exist_ok=True)

    # ---- OpenAI helpers ----
    def _responses_create(
        self,
        *,
        instructions: str,
        input_data: Any,
        previous_response_id: Optional[str] = None,
        tool_choice: Optional[Any] = None,
        parallel_tool_calls: bool = False,
    ):
        kwargs: Dict[str, Any] = {
            "model": MODEL_ID,
            "instructions": instructions,
            "input": input_data,
            "tools": TOOLS_SCHEMA,
            "parallel_tool_calls": parallel_tool_calls,
        }
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        return self.client.responses.create(**kwargs)

    def _execute_tool_call(self, item) -> Dict[str, Any]:
        fname = item.name
        call_id = item.call_id
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            args = {}

        log_args = dict(args)
        if "content" in log_args and isinstance(log_args["content"], str):
            log_args["content"] = f"<{len(log_args['content'])} chars>"
        log(f"Call: {fname}({json.dumps(log_args)})")

        out = ""
        try:
            if fname == "read_source_file":
                rel = _safe_relpath(args["path"])
                p = (self.source_root / rel)
                if p.exists() and p.is_file():
                    out = _read_text_file(p)
                    if len(out) > MAX_TOOL_READ_CHARS:
                        out = out[:MAX_TOOL_READ_CHARS] + f"\n\n-- TRUNCATED at {MAX_TOOL_READ_CHARS} chars --"
                elif p.exists() and p.is_dir():
                    out = f"Error: {rel} is a directory."
                else:
                    out = f"Error: File not found {rel}"

            elif fname == "read_lean_file":
                rel = _safe_relpath(args["path"])
                p = (self.spec_src_root / rel)
                if p.exists() and p.is_file():
                    out = _read_text_file(p)
                    if len(out) > MAX_TOOL_READ_CHARS:
                        out = out[:MAX_TOOL_READ_CHARS] + f"\n\n-- TRUNCATED at {MAX_TOOL_READ_CHARS} chars --"
                elif p.exists() and p.is_dir():
                    out = f"Error: {rel} is a directory."
                else:
                    out = f"Error: Lean file not found {rel}"

            elif fname == "write_lean_file":
                rel = _safe_relpath(args["path"])
                p = (self.spec_src_root / rel)
                _write_text_file(p, args["content"])
                out = f"Written to {p}"

            elif fname == "verify_build":
                out = run_lake_build(self.spec_pkg_root)

            elif fname == "submit_stage":
                out = f"Stage Submitted: {args.get('summary','')}"
                log(out)

            else:
                out = f"Error: Unknown tool {fname}"

        except Exception as e:
            out = f"Tool execution error for {fname}: {e}"

        return {"type": "function_call_output", "call_id": call_id, "output": out}

    def _tool_loop(
        self,
        *,
        instructions: str,
        initial_input: Any,
        tool_choice: Optional[Any] = None,
        max_turns: int = 20,
    ) -> Tuple[str, Optional[str]]:
        """
        Runs a tool-calling loop:
        - Send initial_input
        - Execute any function_call outputs
        - Send function_call_output items back
        Stops when:
        - Model calls submit_stage
        - Model emits no tool calls
        Returns: (last_text, last_response_id)
        """
        previous_response_id: Optional[str] = None
        current_input: Any = initial_input
        last_text = ""

        for turn in range(max_turns):
            log(f"Turn {turn+1}")
            resp = self._responses_create(
                instructions=instructions,
                input_data=current_input,
                previous_response_id=previous_response_id,
                tool_choice=tool_choice,
                parallel_tool_calls=False,
            )
            previous_response_id = resp.id

            tool_calls = []
            saw_submit_stage = False

            if getattr(resp, "output", None):
                for item in resp.output:
                    if item.type == "message":
                        for part in item.content:
                            if part.type == "output_text":
                                last_text = part.text
                                log(f"Model: {trunc(part.text)}")
                    elif item.type == "function_call":
                        if item.name == "submit_stage":
                            saw_submit_stage = True
                        tool_calls.append(item)

            if not tool_calls:
                log("No tool calls. Exiting loop.")
                break

            tool_outputs: List[Dict[str, Any]] = []
            for call in tool_calls:
                tool_outputs.append(self._execute_tool_call(call))

            current_input = tool_outputs

            if saw_submit_stage:
                break

        return last_text, previous_response_id

    # ---- Pipeline pieces ----
    def register_module(self) -> None:
        """Ensure spec/Spec.lean imports Spec.<project>."""
        spec_file = self.spec_src_root.parent / "Spec.lean"  # spec/Spec.lean
        line = f"import Spec.{self.name}"
        if spec_file.exists():
            content = _read_text_file(spec_file)
            if line not in content:
                _write_text_file(spec_file, content.rstrip() + "\n" + line + "\n")
        else:
            _write_text_file(spec_file, line + "\n")

    def _write_root_module(self, module_paths: List[str]) -> None:
        """
        Write spec/Spec/<project>.lean importing all generated submodules.
        module_paths are relative to spec/Spec, like 'order_engine/Engine.lean'.
        """
        imports: List[str] = []
        for rel in module_paths:
            p = Path(rel)
            if p.suffix != ".lean":
                continue
            # Convert path to module name: order_engine/Engine.lean -> Spec.order_engine.Engine
            mod = "Spec." + ".".join(p.with_suffix("").parts)
            imports.append(f"import {mod}")

        root_rel = f"{self.name}.lean"
        body = "\n".join(sorted(set(imports))) + "\n"
        _write_text_file(self.spec_src_root / root_rel, body)
        log(f"Wrote root module {self.spec_src_root / root_rel}")

    def _translate_all_sources(self) -> None:
        files = list_project_files(self.source_root)
        src_files = [f for f in files if _is_source_file(f)]
        if not src_files:
            log("No C/C++ source files found; skipping translation.")
            return

        used_names: Dict[str, int] = {}
        out_paths: List[str] = []

        for rel in src_files:
            src_path = self.source_root / rel
            src_txt = _read_text_file(src_path)

            out_rel = _lean_out_path_for_source(self.name, rel, used_names)
            out_paths.append(out_rel)

            instructions = (
                "You are an Expert Polyglot outputting Lean 4.\n"
                "You must produce a Lean module that typechecks.\n"
                "Hard requirement: call write_lean_file exactly once with the provided output path.\n"
                "At the top, write exactly: `import Spec.Prelude` and do not add other imports (unless purely Spec.*).\n"
                "Do not call submit_stage.\n"
                "Do not wrap code in fences.\n"
                f"Namespace requirement: use `namespace Spec.{self.name}` (and end with `end Spec.{self.name}`).\n"
            )
            user_text = (
                f"Translate this C/C++ source file into Lean 4.\n"
                f"Project: {self.name}\n"
                f"Source relative path: {rel}\n"
                f"Output Lean file path (relative to spec/Spec/): {out_rel}\n\n"
                "Source contents:\n"
                + src_txt
            )

            log(f"Translating {rel} -> {out_rel}")
            forced_write = {"type": "function", "name": "write_lean_file"}

            # One-shot forced tool call: the model must emit write_lean_file
            resp = self._responses_create(
                instructions=instructions,
                input_data=user_text,
                previous_response_id=None,
                tool_choice=forced_write,
                parallel_tool_calls=False,
            )

            calls = [it for it in (resp.output or []) if it.type == "function_call"]
            if not calls:
                raise RuntimeError(f"Model did not call write_lean_file for {rel}. output_text={getattr(resp,'output_text', '')}")

            for c in calls:
                if c.name != "write_lean_file":
                    # With forced function, this should not happen, but handle anyway.
                    log(f"Warning: unexpected tool call {c.name} during forced write.")
                _ = self._execute_tool_call(c)

        # Root module + ensure Spec.lean imports it
        self._write_root_module(out_paths)

    def repair_until_build_targeted(self, label: str) -> None:
        out = run_lake_build_target(self.spec_pkg_root, target=None)
        if out.startswith("Build Success"):
            log(f"{label}: build already passing.")
            return

        log(f"{label}: targeted repair loop starting.")
        for step in range(MAX_REPAIR_TURNS):
            errs = parse_lean_errors(out, max_n=1)
            if not errs:
                # If Lean didn't emit parseable errors, just show tail and use freeform repair
                log("No parseable Lean errors; falling back to model-driven repair.")
                self._repair_until_build_legacy(label, initial_out=out)
                return

            e = errs[0]

            # We only handle errors in Spec/ files here
            if not e.file.startswith("Spec/"):
                log(f"Error not in Spec/: {e.file}. Falling back to freeform repair.")
                self._repair_until_build_legacy(label, initial_out=out)
                return

            # Map "Spec/order_engine/Engine2.lean" -> "order_engine/Engine2.lean"
            rel_under_spec = e.file[len("Spec/"):]
            full_path = self.spec_src_root / rel_under_spec
            if not full_path.exists():
                log(f"File referenced by error not found: {full_path}. Falling back.")
                self._repair_until_build_legacy(label, initial_out=out)
                return

            file_txt = _read_text_file(full_path)
            snippet = excerpt_around(file_txt, e.line, radius=12)

            # Strong nudge: forbid guessing imports + minimal change
            instructions = (
                "You are a Lean 4 build-fixer.\n"
                "Fix EXACTLY the given error with minimal edits.\n"
                "DO NOT invent imports. Prefer `import Spec.Prelude` only.\n"
                "Do not refactor unrelated parts.\n"
                "Hard requirement: you must call write_lean_file exactly once for the faulty file.\n"
                "Return the FULL file content.\n"
            )

            user_text = (
                f"Build error to fix:\n"
                f"FILE: {e.file}\n"
                f"LINE: {e.line}:{e.col}\n"
                f"ERROR: {e.msg}\n\n"
                f"File excerpt:\n{snippet}\n\n"
                f"Rewrite the full file so it compiles, with minimal change.\n"
                f"Path relative to spec/Spec/: {rel_under_spec}\n"
            )

            forced_write = {"type": "function", "name": "write_lean_file"}

            resp = self._responses_create(
                instructions=instructions,
                input_data=user_text,
                tool_choice=forced_write,
                parallel_tool_calls=False,
            )

            calls = [it for it in (resp.output or []) if it.type == "function_call"]
            if not calls:
                raise RuntimeError("Model did not call write_lean_file in targeted repair.")

            for c in calls:
                self._execute_tool_call(c)

            # Validate imports in the updated file
            new_txt = _read_text_file(full_path)
            ok, bad = validate_imports(new_txt, strict=True)
            if not ok:
                log(f"Import policy violation in {rel_under_spec}: {bad}")
                # hard-fix: strip all imports and add Prelude only
                lines = new_txt.splitlines()
                # Remove lines starting with "import"
                cleaned = [ln for ln in lines if not ln.strip().startswith("import ")]
                new_txt2 = "import Spec.Prelude\n\n" + "\n".join(cleaned).lstrip()
                _write_text_file(full_path, new_txt2)
                log("Auto-sanitized imports to `import Spec.Prelude`.")

            # Build just the failing module first (faster)
            target_mod = module_name_from_lean_path(rel_under_spec)
            out = run_lake_build_target(self.spec_pkg_root, target=target_mod)
            log(f"Partial build {target_mod}: {trunc(out, 500)}")
            
            if out.startswith("Build Success"):
                # verify full build
                out2 = run_lake_build_target(self.spec_pkg_root, target=None)
                if out2.startswith("Build Success"):
                    log(f"{label}: build fully repaired.")
                    return
                out = out2

        log(f"{label}: repair loop exhausted; still failing.")

    def _repair_until_build_legacy(self, label: str, initial_out: str | None = None) -> None:
        """
        Legacy loop: freeform repair if we can't parse errors.
        """
        res = initial_out or run_lake_build(self.spec_pkg_root)
        if res.startswith("Build Success"):
            return

        log(f"{label}: entering legacy repair")
        log(trunc(res, 4000))

        allowed = {
            "type": "allowed_tools",
            "mode": "required",
            "tools": [
                {"type": "function", "name": "read_lean_file"},
                {"type": "function", "name": "write_lean_file"},
                {"type": "function", "name": "verify_build"},
            ],
        }

        instructions = (
            "You are a Lean 4 build-fixer.\n"
            "Goal: make `lake build` succeed.\n"
            "Use read_lean_file/write_lean_file/verify_build.\n"
            "Do not invent new dependencies.\n"
        )
        initial_input = (
            f"Build Failed:\n{res}\n\n"
            f"Files:\n" + "\n".join(list_lean_files(self.spec_src_root))
        )

        _, _ = self._tool_loop(
            instructions=instructions,
            initial_input=initial_input,
            tool_choice=allowed,
            max_turns=10,
        )

    def run_stage_translation(self) -> None:
        log("--- Stage: Translation ---")
        self._translate_all_sources()
        self.repair_until_build_targeted("Translation")

    def run_stage_equivalence(self) -> None:
        log("--- Stage: Equivalence ---")

        # Provide the model enough context to write tests, then FORCE it to write Test.lean.
        lean_files = list_lean_files(self.spec_src_root)
        project_files = [p for p in lean_files if p.startswith(f"{self.name}/")]
        key_files = project_files[:8]  # cap context

        snippets: List[str] = []
        for rel in key_files:
            p = self.spec_src_root / rel
            try:
                txt = _read_text_file(p)
            except Exception:
                txt = ""
            snippets.append(f"FILE: {rel}\n{txt}\n")

        instructions = (
            "You are a QA Engineer for Lean 4.\n"
            "Create a Lean test module that adds executable-style constraints via `example` or small theorems.\n"
            "Hard requirement: call write_lean_file exactly once to write the requested Test.lean file.\n"
            "Use `import Spec.Prelude` and `import Spec.<Project>...`.\n"
            "The test file must compile.\n"
            "Do not call submit_stage.\n"
        )
        out_rel = f"{self.name}/Test.lean"
        user_text = (
            f"Project: {self.name}\n"
            f"Write tests to: {out_rel}\n\n"
            "Existing translated Lean files:\n" + "\n".join(project_files) + "\n\n"
            "Here are contents of some key files:\n\n" + "\n\n".join(snippets)
        )

        forced_write = {"type": "function", "name": "write_lean_file"}
        resp = self._responses_create(
            instructions=instructions,
            input_data=user_text,
            tool_choice=forced_write,
            parallel_tool_calls=False,
        )
        calls = [it for it in (resp.output or []) if it.type == "function_call"]
        if not calls:
            raise RuntimeError("Model did not call write_lean_file for Test.lean")
        for c in calls:
            _ = self._execute_tool_call(c)

        self.repair_until_build_targeted("Equivalence")

    def run_stage_specification(self) -> None:
        log("--- Stage: Specification ---")

        lean_files = list_lean_files(self.spec_src_root)
        project_files = [p for p in lean_files if p.startswith(f"{self.name}/")]

        snippets: List[str] = []
        for rel in project_files[:8]:
            p = self.spec_src_root / rel
            try:
                txt = _read_text_file(p)
            except Exception:
                txt = ""
            snippets.append(f"FILE: {rel}\n{txt}\n")

        instructions = (
            "You are a Formal Verification Engineer for Lean 4.\n"
            "Create a Verif.lean file that states intended invariants and theorems.\n"
            "It is allowed to use `sorry` for proofs, but the file must parse and typecheck.\n"
            "Hard requirement: call write_lean_file exactly once to write the requested Verif.lean file.\n"
            "Use `import Spec.Prelude`.\n"
            "Do not call submit_stage.\n"
        )
        out_rel = f"{self.name}/Verif.lean"
        user_text = (
            f"Project: {self.name}\n"
            f"Write specification to: {out_rel}\n\n"
            "Existing translated Lean files:\n" + "\n".join(project_files) + "\n\n"
            "Here are contents of some key files:\n\n" + "\n\n".join(snippets)
        )

        forced_write = {"type": "function", "name": "write_lean_file"}
        resp = self._responses_create(
            instructions=instructions,
            input_data=user_text,
            tool_choice=forced_write,
            parallel_tool_calls=False,
        )
        calls = [it for it in (resp.output or []) if it.type == "function_call"]
        if not calls:
            raise RuntimeError("Model did not call write_lean_file for Verif.lean")
        for c in calls:
            _ = self._execute_tool_call(c)

        self.repair_until_build_targeted("Specification")

    def run_stage_verification(self) -> None:
        target_file = self.spec_project_root / "Verif.lean"
        if not target_file.exists():
            log("No Verif.lean found. Skipping Aristotle.")
            return
        if not aristotlelib:
            log("aristotlelib missing. Skipping Aristotle.")
            return

        log("=== Aristotle Verification ===")
        os.environ["ARISTOTLE_API_KEY"] = self.secrets["secrets"].get("ARISTOTLE_API_KEY", "")

        try:
            cwd = os.getcwd()
            os.chdir(self.spec_pkg_root)

            rel_target = target_file.relative_to(self.spec_pkg_root)
            log(f"Submitting {rel_target} to Aristotle...")

            result = asyncio.run(
                aristotlelib.Project.prove_from_file(
                    input_file_path=str(rel_target),
                    auto_add_imports=True,
                    validate_lean_project=True,
                    wait_for_completion=True,
                )
            )

            os.chdir(cwd)
            log(f"Aristotle Output: {result}")

            res_path = self.spec_pkg_root / result
            if res_path.exists():
                res_path.rename(target_file)
                log("Verified spec saved over Verif.lean.")
                bres = run_lake_build(self.spec_pkg_root)
                log(f"Final Build: {bres}")

        except Exception as e:
            log(f"Aristotle Error: {e}")
            os.chdir(cwd)

    # ---- Main runner ----
    def run(self) -> None:
        log(f"=== Processing Project: {self.name} ===")
        ensure_prelude()
        self.register_module()

        self.run_stage_translation()
        self.run_stage_equivalence()
        self.run_stage_specification()
        self.run_stage_verification()


# ---------------- Main ----------------
def main() -> None:
    log("=== Anneal Universal Verification Agent ===")
    secrets = load_secrets()
    client = OpenAI(api_key=secrets["secrets"]["OPENAI_API_KEY"])

    if not EXAMPLES_DIR.exists():
        log(f"No examples found in {EXAMPLES_DIR}")
        return

    examples = [d for d in EXAMPLES_DIR.iterdir() if d.is_dir()]
    if not examples:
        log("No examples found.")
        return

    for ex in examples:
        proc = ProjectProcessor(ex.name, ex, client, secrets)
        proc.run()


if __name__ == "__main__":
    main()
