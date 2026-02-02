"""LLM integration and tool execution."""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from google.genai import types
from helpers import (log, run_lake_build, run_lake_build_target, validate_basic_lean_shape, is_writable,
                     MODEL_ID, TOOLS_SCHEMA, MAX_TOOL_READ_CHARS, SPEC_DIR, SPEC_SRC_DIR)

class RestartTranslationError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

_GEMINI_TOOLS = None

def get_gemini_tools() -> types.Tool:
    global _GEMINI_TOOLS
    if _GEMINI_TOOLS is None:
        _GEMINI_TOOLS = types.Tool(function_declarations=[
            types.FunctionDeclaration(name=t["name"], description=t["description"], parameters_json_schema=t["parameters"])
            for t in TOOLS_SCHEMA
        ])
    return _GEMINI_TOOLS

def tool_output_item(call_id: str, out: str, name: str = "unknown") -> Dict[str, Any]:
    return {"call_id": call_id, "output": out, "name": name, "type": "function_call_output"}

def responses_create(ctx: dict, *, instructions: str, input_data: Any, **_):
    """
    Wrapper for Gemini API call.
    - instructions: The system prompt (Persona).
    - input_data: The chat history.
    - tools: The function definitions (schema).
    """
    contents = input_data if isinstance(input_data, list) else [types.Content(role="user", parts=[types.Part.from_text(text=str(input_data))])]
    config = types.GenerateContentConfig(
        system_instruction=instructions,
        tools=[get_gemini_tools()],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    # Note: Retries are handled by the 'tenacity' library upstream if configured,
    # or by the built-in client depending on version.
    return ctx["client"].models.generate_content(model=MODEL_ID, contents=contents, config=config)

def update_test_state_from_report(ctx: dict, report_json: str) -> None:
    try:
        rep = json.loads(report_json)
        ctx["equiv_state"]["last_report"] = rep
        ctx["equiv_state"]["last_status"] = rep.get("status", "unknown")
        ctx["equiv_state"]["passed_runs"] = rep.get("passed_runs", 0)
    except Exception:
        ctx["equiv_state"]["last_status"] = "malformed"
        ctx["equiv_state"]["passed_runs"] = 0


def can_submit_current_stage(ctx: dict) -> Tuple[bool, str]:
    if not run_lake_build(SPEC_DIR).startswith("Build Success"):
        return False, "Build failed"
    if ctx["equiv_state"]["last_status"] != "success":
        return False, "Differential tests not passed"
    return True, ""

def _safe_relpath(p: str) -> str:
    """Security check: Prevent path traversal (e.g. ../../etc/passwd)."""
    p = (p or "").replace("\\", "/").lstrip("/")
    if ".." in p: raise ValueError("Path traversal not allowed")
    return p

def execute_tool_call(ctx: dict, item, run_differential_test_impl) -> Tuple[Dict[str, Any], bool]:
    """
    Dispatch function: Maps tool name (str) -> Python logic.
    Returns: (output_dict, success_bool)
    """
    fname = item.name
    call_id = f"call_{fname}_{id(item)}"
    args = item.args if hasattr(item, 'args') and isinstance(item.args, dict) else {}
    
    try:
        if fname == "restart_translation":
            raise RestartTranslationError(args.get("reason", "No reason"))

        if fname == "read_source_file":
            rel = _safe_relpath(args["path"])
            p = Path("generated") / rel
            if p.exists() and p.is_file():
                return tool_output_item(call_id, p.read_text()[:MAX_TOOL_READ_CHARS]), True
            return tool_output_item(call_id, f"Error: Not found {rel}"), True

        if fname == "read_lean_file":
            rel = _safe_relpath(args["path"])
            p = SPEC_SRC_DIR / rel
            if p.exists() and p.is_file():
                return tool_output_item(call_id, p.read_text()[:MAX_TOOL_READ_CHARS]), True
            return tool_output_item(call_id, f"Error: Not found {rel}"), True

        if fname == "write_lean_file":
            rel = _safe_relpath(args["path"])
            full_path = f"spec/Src/{rel}"
            if not is_writable(full_path):
                log(f"  ✗ Write denied: {rel}")
                return tool_output_item(call_id, f"Denied: {rel} not writable"), False
            content = args.get("content", "")
            ok, reason = validate_basic_lean_shape(rel, content)
            if not ok:
                log(f"  ✗ Rejected: {rel} - {reason}")
                return tool_output_item(call_id, f"Rejected: {reason}"), False
            p = SPEC_SRC_DIR / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            log(f"  ✓ Wrote {rel} ({len(content)} chars)")
            # Invalidate verification state because code changed
            ctx["equiv_state"]["last_status"] = "modified"
            return tool_output_item(call_id, f"Written to {p}"), True

        if fname == "write_text_file":
            # Used for C files (and other temp files).
            rel = _safe_relpath(args["path"])
            if not is_writable(rel):
                return tool_output_item(call_id, f"Denied: {rel} not writable"), False
            content = args.get("content", "")
            if not content.strip():
                return tool_output_item(call_id, "Rejected: empty content"), False
            p = Path(rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            # Invalidate verification state because code changed
            ctx["equiv_state"]["last_status"] = "modified"
            return tool_output_item(call_id, f"Written to {p}"), True

        if fname == "verify_build":
            # Compile C sources first
            import subprocess
            gen_dir = Path("generated")
            c_files = list(gen_dir.glob("*.c")) if gen_dir.exists() else []
            if c_files:
                log(f"  [Build] compiling {len(c_files)} C file(s)...")
                for src in c_files:
                    r = subprocess.run(["gcc", "-fsyntax-only", "-Wall", str(src)], capture_output=True, text=True)
                    if r.returncode != 0:
                        log(f"  ✗ C compile failed: {src.name}")
                        return tool_output_item(call_id, f"C compile error in {src.name}:\n{r.stderr[:1500]}"), True
                log("  ✓ C syntax OK")
            
            log("  [Build] lake build...")
            out = run_lake_build(SPEC_DIR)
            if out.startswith("Build Success"):
                log("  ✓ Build Success")
            else:
                log(f"  ✗ Build Failed:\n{out[:1500]}")
            return tool_output_item(call_id, out), True

        if fname == "run_differential_test":
            # The heart of verification. See diff_test.py.
            out_json = run_differential_test_impl(ctx, args)
            update_test_state_from_report(ctx, out_json)
            return tool_output_item(call_id, out_json), True

        if fname == "submit_stage":
            ok, why = can_submit_current_stage(ctx)
            if not ok:
                return tool_output_item(call_id, f"Denied: {why}"), False
            summary = args.get('summary', '')
            ctx["equiv_state"]["submit_summary"] = summary
            return tool_output_item(call_id, f"Stage Submitted: {summary}"), True

        return tool_output_item(call_id, f"Unknown tool: {fname}"), True

    except RestartTranslationError:
        raise
    except Exception as e:
        return tool_output_item(call_id, f"Error: {e}"), False
