"""LLM integration and tool execution."""
# This module coordinates interactions with the Gemini API and executes 
# the tools (commands/file operations) requested by the LLM agent.
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from google.genai import types
from helpers import (log, run_lake_build, run_lake_build_target, validate_basic_lean_shape, is_writable,
                     MODEL_ID, TOOLS_SCHEMA, MAX_TOOL_READ_CHARS, SPEC_DIR, SPEC_SRC_DIR)

# Custom exception to handle agent-initiated restarts.
class RestartTranslationError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

# Global cache for the tool definitions to avoid redundant schema generation.
_GEMINI_TOOLS = None

def get_gemini_tools() -> types.Tool:
    """Prepare the function declarations for the Gemini API."""
    global _GEMINI_TOOLS
    if _GEMINI_TOOLS is None:
        # Convert our simplified TOOLS_SCHEMA into the expected Google SDK format.
        _GEMINI_TOOLS = types.Tool(function_declarations=[
            types.FunctionDeclaration(name=t["name"], description=t["description"], parameters_json_schema=t["parameters"])
            for t in TOOLS_SCHEMA
        ])
    return _GEMINI_TOOLS

# Formats a single tool execution result for the LLM history.
def tool_output_item(call_id: str, out: str, name: str = "unknown") -> Dict[str, Any]:
    return {"call_id": call_id, "output": out, "name": name, "type": "function_call_output"}

def generate_content_with_retry(client, model, contents, config=None):
    """
    Wrapper for generate_content with robust rate limit handling.
    Catches errors 5 times (6 attempts total), sleeping 60s on each fail.
    """
    # Linear backoff logic to deal with Resource Exhausted (429) errors.
    for attempt in range(6):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:
            if attempt < 5:
                # Log the failure and wait for quota reset.
                log(f"API Error (attempt {attempt+1}/6): {e}. Sleeping 60s...") 
                time.sleep(60)
            else:
                # Permanent failure after all retries.
                raise e

def responses_create(ctx: dict, *, instructions: str, input_data: Any, **_):
    """
    Wrapper for Gemini API call.
    - instructions: The system prompt (Persona).
    - input_data: The chat history.
    - tools: The function definitions (schema).
    """
    # Normalize history to the List[Content] format expected by the SDK.
    contents = input_data if isinstance(input_data, list) else [types.Content(role="user", parts=[types.Part.from_text(text=str(input_data))])]
    # Configure the session: set the system prompt and enable our custom tools.
    config = types.GenerateContentConfig(
        system_instruction=instructions,
        tools=[get_gemini_tools()],
        # We handle function execution manually in our local look.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    # Perform the generation with retry logic.
    return generate_content_with_retry(ctx["client"], MODEL_ID, contents, config)

# Update the persistent verification state based on tool outputs.
def update_test_state_from_report(ctx: dict, report_json: str) -> None:
    try:
        rep = json.loads(report_json)
        ctx["equiv_state"]["last_report"] = rep
        ctx["equiv_state"]["last_status"] = rep.get("status", "unknown")
        ctx["equiv_state"]["passed_runs"] = rep.get("passed_runs", 0)
    except Exception:
        ctx["equiv_state"]["last_status"] = "malformed"
        ctx["equiv_state"]["passed_runs"] = 0

# Check conditions for stage submission (build must pass, tests must pass).
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
    # Recover arguments from the Tool Call content.
    args = item.args if hasattr(item, 'args') and isinstance(item.args, dict) else {}
    
    try:
        # AGENT ACTION: Restart the current session.
        if fname == "restart_translation":
            raise RestartTranslationError(args.get("reason", "No reason"))

        # AGENT ACTION: Inspect a generated C file.
        if fname == "read_source_file":
            rel = _safe_relpath(args["path"])
            p = Path("generated") / rel
            if p.exists() and p.is_file():
                # Limit output size to prevent context window explosion.
                return tool_output_item(call_id, p.read_text()[:MAX_TOOL_READ_CHARS]), True
            return tool_output_item(call_id, f"Error: Not found {rel}"), True

        # AGENT ACTION: Inspect a Lean specification file.
        if fname == "read_lean_file":
            rel = _safe_relpath(args["path"])
            p = SPEC_SRC_DIR / rel
            if p.exists() and p.is_file():
                return tool_output_item(call_id, p.read_text()[:MAX_TOOL_READ_CHARS]), True
            return tool_output_item(call_id, f"Error: Not found {rel}"), True

        # AGENT ACTION: Update/Create a Lean specification.
        if fname == "write_lean_file":
            rel = _safe_relpath(args["path"])
            full_path = f"spec/Src/{rel}"
            # Check write permissions relative to the workspace rules.
            if not is_writable(full_path):
                log(f"  ✗ Write denied: {rel}")
                return tool_output_item(call_id, f"Denied: {rel} not writable"), False
            content = args.get("content", "")
            # Basic validation to prevent immediate compilation errors.
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

        # AGENT ACTION: Update/Create non-Lean files (C code, Makefiles, etc).
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

        # AGENT ACTION: Trigger a Lean 4 build check.
        if fname == "verify_build":
            # Compile C sources first to find obvious syntax errors early.
            import subprocess
            gen_dir = Path("generated")
            c_files = list(gen_dir.glob("*.c")) if gen_dir.exists() else []
            if c_files:
                log(f"  [Build] compiling {len(c_files)} C file(s)...")
                for src in c_files:
                    # Uses -fsyntax-only to speed up verification check.
                    r = subprocess.run(["gcc", "-fsyntax-only", "-Wall", str(src)], capture_output=True, text=True)
                    if r.returncode != 0:
                        log(f"  ✗ C compile failed: {src.name}")
                        return tool_output_item(call_id, f"C compile error in {src.name}:\n{r.stderr[:1500]}"), True
                log("  ✓ C syntax OK")
            
            # Execute Lean project build via Lake.
            log("  [Build] lake build...")
            out = run_lake_build(SPEC_DIR)
            if out.startswith("Build Success"):
                log("  ✓ Build Success")
            else:
                log(f"  ✗ Build Failed:\n{out[:1500]}")
            return tool_output_item(call_id, out), True

        # AGENT ACTION: Execute fuzzing loops to verify C-Lean equivalence.
        if fname == "run_differential_test":
            # The heart of verification. See diff_test.py.
            out_json = run_differential_test_impl(ctx, args)
            update_test_state_from_report(ctx, out_json)
            return tool_output_item(call_id, out_json), True

        # AGENT ACTION: Complete the current stage.
        if fname == "submit_stage":
            ok, why = can_submit_current_stage(ctx)
            if not ok:
                return tool_output_item(call_id, f"Denied: {why}"), False
            summary = args.get('summary', '')
            ctx["equiv_state"]["submit_summary"] = summary
            return tool_output_item(call_id, f"Stage Submitted: {summary}"), True

        # Fallback for unsupported tool names.
        return tool_output_item(call_id, f"Unknown tool: {fname}"), True

    except RestartTranslationError:
        # Rethrow to the session loop.
        raise
    except Exception as e:
        # Capture and report generic tool failures.
        return tool_output_item(call_id, f"Error: {e}"), False
