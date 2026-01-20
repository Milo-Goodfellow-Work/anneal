"""
Anneal Stages - Shared LLM and tool execution functions.

This module contains the procedural functions for interacting with the
Google Gemini API and executing tool calls.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from google.genai import types

from helpers import (
    log, trunc, _safe_relpath, _read_text_file, _write_text_file,
    run_lake_build, run_lake_build_target,
    validate_basic_lean_shape, MODEL_ID, TOOLS_SCHEMA,
    MAX_TOOL_READ_CHARS, DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN,
)


class RestartTranslationError(Exception):
    """Raised when the model decides the translation is fundamentally flawed."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _convert_tools_to_gemini() -> types.Tool:
    """Convert TOOLS_SCHEMA to Gemini FunctionDeclaration format."""
    declarations = []
    for tool in TOOLS_SCHEMA:
        decl = types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters_json_schema=tool["parameters"],
        )
        declarations.append(decl)
    return types.Tool(function_declarations=declarations)


# Cached Gemini tools - convert once
_GEMINI_TOOLS = None

def get_gemini_tools() -> types.Tool:
    """Get the Gemini-formatted tools (cached)."""
    global _GEMINI_TOOLS
    if _GEMINI_TOOLS is None:
        _GEMINI_TOOLS = _convert_tools_to_gemini()
    return _GEMINI_TOOLS


def tool_output_item(call_id: str, out: str, name: str = "unknown") -> Dict[str, Any]:
    """Create a tool output item for the API."""
    return {"call_id": call_id, "output": out, "name": name, "type": "function_call_output"}


def responses_create(
    ctx: dict,
    *,
    instructions: str,
    input_data: Any,
    previous_response_id: Optional[str] = None,
    tool_choice: Optional[Any] = None,
    parallel_tool_calls: bool = False,
):
    """Create a response from the Gemini API.
    
    Args:
        ctx: Context with 'client' (Gemini client) and 'chat' (optional Chat session)
        instructions: System instructions for the model
        input_data: Either a string prompt or list of content items (for multi-turn)
        previous_response_id: Unused (Gemini uses Chat sessions instead)
        tool_choice: Unused (Gemini has different mechanism)
        parallel_tool_calls: Unused
    """
    # Build the contents
    if isinstance(input_data, str):
        contents = input_data
    elif isinstance(input_data, list):
        # Convert from OpenAI format to Gemini format
        contents = []
        for item in input_data:
            if isinstance(item, str):
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=item)]))
            elif isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "function_call_output":
                    # Tool response
                    contents.append(types.Content(
                        role="tool",
                        parts=[types.Part.from_function_response(
                            name=item.get("name", "unknown"),
                            response={"result": item.get("output", "")},
                        )]
                    ))
                elif "role" in item:
                    # Standard message
                    role = "user" if item["role"] == "user" else "model"
                    text = item.get("content", "") or item.get("text", "")
                    contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
            else:
                # Assume it's already a Content object
                contents.append(item)
    else:
        contents = str(input_data)
    
    # Configure the request
    config = types.GenerateContentConfig(
        system_instruction=instructions,
        tools=[get_gemini_tools()],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    
    # Make the request
    response = ctx["client"].models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=config,
    )
    
    return response


def persist_equiv_report_if_success(ctx: dict) -> None:
    """Persist equivalence report if successful."""
    rep = ctx["equiv_state"].get("last_report")
    if not isinstance(rep, dict):
        return
    if rep.get("status") != "success":
        return
    payload = {
        "status": "success",
        "saved_at_unix": int(time.time()),
        "passed_runs": rep.get("passed_runs"),
        "required_runs": rep.get("required_runs"),
        "min_cases_per_run": rep.get("min_cases_per_run"),
        "runs": rep.get("runs"),
        "total_time_s": rep.get("total_time_s"),
    }
    _write_text_file(Path(ctx["equiv_report_rel"]), json.dumps(payload, indent=2, sort_keys=True) + "\n")


def update_test_state_from_report(ctx: dict, report_json: str) -> None:
    """Update equivalence state from a test report."""
    try:
        rep = json.loads(report_json)
    except Exception:
        ctx["equiv_state"]["last_report"] = report_json
        ctx["equiv_state"]["last_status"] = "malformed_report"
        ctx["equiv_state"]["passed_runs"] = 0
        return

    ctx["equiv_state"]["last_report"] = rep
    ctx["equiv_state"]["last_status"] = rep.get("status", "unknown")
    ctx["equiv_state"]["passed_runs"] = rep.get("passed_runs", 0)
    ctx["equiv_state"]["required_runs"] = rep.get("required_runs", DIFF_REQUIRED_RUNS)
    ctx["equiv_state"]["min_cases_per_run"] = rep.get("min_cases_per_run", DIFF_MIN_CASES_PER_RUN)


def can_submit_current_stage(ctx: dict) -> Tuple[bool, str]:
    """Check if the current stage can be submitted."""
    stage = ctx["current_stage"].upper()

    # For Co-Generation stage: require build success + passing diff tests
    if stage == "COGENERATION":
        b = run_lake_build(ctx["spec_pkg_root"])
        if not b.startswith("Build Success"):
            return False, "lake build is not successful; fix build errors first."
        
        # Require harness to build
        hb = run_lake_build_target(ctx["spec_pkg_root"], target="Spec.tests.Harness")
        if not hb.startswith("Build Success"):
            return False, "harness build failed; fix Spec.tests.Harness compilation errors."

        # Require differential tests to pass
        rep = ctx["equiv_state"].get("last_report")
        if not rep:
            return False, "no differential test report yet; you must call run_differential_test."
        if ctx["equiv_state"].get("last_status") != "success":
            return False, "differential testing has not succeeded; fix timeouts/diffs and rerun."
        if ctx["equiv_state"].get("passed_runs", 0) < ctx["equiv_state"].get("required_runs", DIFF_REQUIRED_RUNS):
            return False, f"insufficient successful runs; need {DIFF_REQUIRED_RUNS} passing seeds."
        return True, ""

    # Legacy stages (for backward compatibility during transition)
    if stage in ("EQUIVALENCE", "HARDENING", "SPECIFICATION"):
        b = run_lake_build(ctx["spec_pkg_root"])
        if not b.startswith("Build Success"):
            return False, "lake build is not successful; fix build errors first."
        if stage in ("EQUIVALENCE", "HARDENING"):
            hb = run_lake_build_target(ctx["spec_pkg_root"], target="Spec.tests.Harness")
            if not hb.startswith("Build Success"):
                return False, "harness build failed; fix Spec.tests.Harness compilation errors."

    if stage == "EQUIVALENCE":
        rep = ctx["equiv_state"].get("last_report")
        if not rep:
            return False, "no differential test report yet; you must call run_differential_test."
        if ctx["equiv_state"].get("last_status") != "success":
            return False, "differential testing has not succeeded; fix timeouts/diffs and rerun."
        if ctx["equiv_state"].get("passed_runs", 0) < ctx["equiv_state"].get("required_runs", DIFF_REQUIRED_RUNS):
            return False, f"insufficient successful runs; need {DIFF_REQUIRED_RUNS} passing seeds."
        return True, ""

    if stage == "HARDENING":
        if not Path(ctx["safety_case_rel"]).exists():
            return False, "safety case markdown file not written yet; write it to spec/reports/<project>_SafetyCase.md."
        if ctx["equiv_state"].get("last_status") != "success":
            return False, "differential testing not successful after hardening; rerun and fix."
        if ctx["equiv_state"].get("passed_runs", 0) < DIFF_REQUIRED_RUNS:
            return False, f"need {DIFF_REQUIRED_RUNS} passing seeds after hardening."
        return True, ""

    return True, ""


def execute_tool_call(ctx: dict, item, run_differential_test_impl) -> Tuple[Dict[str, Any], bool]:
    """
    Execute a single tool call from the model.
    Returns (function_call_output_item, success_flag).
    
    run_differential_test_impl is passed in to avoid circular imports.
    
    Note: Gemini FunctionCall has .name and .args (dict).
    OpenAI had .call_id and .arguments (JSON string).
    """
    fname = item.name
    # Gemini doesn't have call_id, generate one
    call_id = getattr(item, 'call_id', None) or f"call_{fname}_{id(item)}"
    
    # Gemini uses .args as a dict directly
    if hasattr(item, 'args') and isinstance(item.args, dict):
        args = item.args
    elif hasattr(item, 'arguments'):
        # OpenAI format fallback
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            args = {}
    else:
        args = {}

    # Log args (hide content)
    log_args = dict(args)
    if "content" in log_args and isinstance(log_args["content"], str):
        log_args["content"] = f"<{len(log_args['content'])} chars>"
    log(f"Call: {fname}({json.dumps(log_args)})")

    try:
        if fname == "restart_translation":
            reason = (args.get("reason") or "").strip()
            if not reason:
                reason = "No reason provided."
            raise RestartTranslationError(reason)

        if fname == "read_source_file":
            rel = _safe_relpath(args["path"])
            p = ctx["source_root"] / rel
            if p.exists() and p.is_file():
                out = _read_text_file(p)
                if len(out) > MAX_TOOL_READ_CHARS:
                    out = out[:MAX_TOOL_READ_CHARS] + f"\n\n-- TRUNCATED at {MAX_TOOL_READ_CHARS} chars --"
                return tool_output_item(call_id, out), True
            if p.exists() and p.is_dir():
                return tool_output_item(call_id, f"Error: {rel} is a directory."), True
            return tool_output_item(call_id, f"Error: File not found {rel}"), True

        if fname == "read_lean_file":
            rel = _safe_relpath(args["path"]).replace("\\", "/")

            # Anti-smuggling: prevent reading Verif.lean before Equivalence has passed
            if rel == f"{ctx['name']}/Verif.lean":
                stage = ctx["current_stage"].upper()
                if stage not in ("SPECIFICATION", "HARDENING", "VERIFICATION"):
                    if ctx["equiv_state"].get("last_status") != "success":
                        return tool_output_item(call_id, "Denied: Verif.lean is unavailable until after Equivalence succeeds."), False

            p = ctx["spec_src_root"] / rel
            if p.exists() and p.is_file():
                out = _read_text_file(p)
                if len(out) > MAX_TOOL_READ_CHARS:
                    out = out[:MAX_TOOL_READ_CHARS] + f"\n\n-- TRUNCATED at {MAX_TOOL_READ_CHARS} chars --"
                return tool_output_item(call_id, out), True
            if p.exists() and p.is_dir():
                return tool_output_item(call_id, f"Error: {rel} is a directory."), True
            return tool_output_item(call_id, f"Error: Lean file not found {rel}"), True

        if fname == "write_lean_file":
            rel = _safe_relpath(args["path"]).replace("\\", "/")

            # Stage-gated anti-smuggling
            if rel == f"{ctx['name']}/Verif.lean":
                stage = ctx["current_stage"].upper()
                if stage not in ("SPECIFICATION", "HARDENING", "VERIFICATION"):
                    return tool_output_item(call_id, "Denied: Verif.lean is locked until Specification/Hardening."), False
                if ctx["equiv_state"].get("last_status") != "success":
                    return tool_output_item(call_id, "Denied: Equivalence has not succeeded; Verif.lean remains locked."), False

            # Enforce file-level lockdown
            if rel in ctx["locked_lean_paths"]:
                msg = f"Denied: '{rel}' is locked (read-only). Locked: {sorted(ctx['locked_lean_paths'])}"
                return tool_output_item(call_id, msg), False

            # Enforce allowlist
            if rel not in ctx["allowed_lean_writes"]:
                msg = f"Denied: '{rel}' is not in the autogenerated writable set. You may only write these Lean files:\n" + "\n".join(sorted(ctx["allowed_lean_writes"]))
                return tool_output_item(call_id, msg), False

            content = args.get("content", "")
            ok, reason = validate_basic_lean_shape(ctx["name"], rel, content)
            if not ok:
                return tool_output_item(call_id, f"Rejected content for '{rel}': {reason}"), False

            p = ctx["spec_src_root"] / rel
            _write_text_file(p, content)
            return tool_output_item(call_id, f"Written to {p}"), True

        if fname == "write_text_file":
            rel = _safe_relpath(args["path"]).replace("\\", "/")

            # Check explicit allowlist first
            allowed = rel in ctx["allowed_text_writes"]
            
            # In prompt mode, also allow writes under the source_root (generated impl files)
            if not allowed and ctx.get("prompt"):
                source_root_rel = str(ctx["source_root"]).replace("\\", "/")
                if rel.startswith(source_root_rel + "/") or rel.startswith("generated/"):
                    allowed = True
            
            if not allowed:
                msg = f"Denied: '{rel}' is not in the writable set. Allowed: {sorted(ctx['allowed_text_writes'])}"
                return tool_output_item(call_id, msg), False

            p = Path(rel)
            content = args.get("content", "")
            if not content.strip():
                return tool_output_item(call_id, f"Rejected: '{rel}' content is empty."), False

            _write_text_file(p, content)
            return tool_output_item(call_id, f"Written to {p}"), True

        if fname == "verify_build":
            out = run_lake_build(ctx["spec_pkg_root"])
            return tool_output_item(call_id, out), True

        if fname == "run_differential_test":
            out_json = run_differential_test_impl(ctx, args)
            log(f"[DiffTest Result] {out_json}")
            update_test_state_from_report(ctx, out_json)
            persist_equiv_report_if_success(ctx)
            return tool_output_item(call_id, out_json), True

        if fname == "submit_stage":
            ok, why = can_submit_current_stage(ctx)
            if not ok:
                return tool_output_item(call_id, f"Denied submit_stage: {why}"), False
            out = f"Stage Submitted: {args.get('summary', '')}"
            log(out)
            return tool_output_item(call_id, out), True

        return tool_output_item(call_id, f"Error: Unknown tool {fname}"), True

    except RestartTranslationError:
        raise
    except Exception as e:
        return tool_output_item(call_id, f"Tool execution error for {fname}: {e}"), False
