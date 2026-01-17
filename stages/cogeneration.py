"""
Anneal Stages - Co-Generation stage implementation.

Stage 1 of the 2-stage pipeline:
- Prompt Mode: Generates implementation + Lean from natural language
- Legacy Mode: Translates existing C to Lean

The output is verified-equivalent impl + Lean code (definitions only, no specs).
"""
from __future__ import annotations
import json
from typing import Optional, Any, List, Dict
from pathlib import Path

from helpers import (
    log, trunc, _read_text_file, _limit_lines, run_lake_build,
    MAX_SESSION_TURNS, DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN,
)
from stages.llm import responses_create, execute_tool_call
from stages.prompts import base_instructions_cogen, base_instructions_prompt_cogen
from stages.diff_test import run_differential_test_impl


def _session_cogeneration(
    ctx: dict,
    *,
    instructions: str,
    user_payload: str,
    max_turns: int = MAX_SESSION_TURNS * 4,
) -> bool:
    """
    Run the co-generation session until:
    1. Code is generated in both languages
    2. Differential tests pass robustly (5 runs x 5 cases)
    """
    previous_response_id: Optional[str] = None
    current_input: Any = user_payload

    for turn in range(max_turns):
        log(f"[CoGen] Turn {turn+1}/{max_turns}")
        resp = responses_create(
            ctx,
            instructions=instructions,
            input_data=current_input,
            previous_response_id=previous_response_id,
            tool_choice=None,
            parallel_tool_calls=False,
        )
        previous_response_id = resp.id

        # Extract tool calls from response
        tool_calls = []
        if getattr(resp, "output", None):
            for item in resp.output:
                if item.type == "message":
                    for part in item.content:
                        if part.type == "output_text":
                            log(f"Model: {trunc(part.text, 800)}")
                elif item.type == "function_call":
                    tool_calls.append(item)

        if not tool_calls:
            current_input = (
                "NO TOOL CALLS DETECTED.\n"
                "You MUST call tools to make progress.\n"
                "Next steps:\n"
                "1. Write implementation code\n"
                "2. Write Lean definitions\n"
                "3. Update test harnesses\n"
                "4. Run differential tests\n"
                "5. Call submit_stage when tests pass robustly\n"
            )
            continue

        tool_outputs: List[Dict[str, Any]] = []
        submit_ok = False

        for call in tool_calls:
            out_item, ok = execute_tool_call(ctx, call, run_differential_test_impl)
            tool_outputs.append(out_item)
            if call.name == "submit_stage" and ok:
                submit_ok = True

        current_input = tool_outputs

        if submit_ok:
            return True

    log("[CoGen] Session exceeded max turns without successful completion.")
    return False


def _build_prompt_payload(ctx: dict) -> str:
    """Build the user payload for prompt-driven generation."""
    prompt = ctx.get("prompt", "No prompt provided")
    language = ctx.get("language", "c").upper()
    
    return (
        f"TASK: Generate a {language} implementation AND equivalent Lean code\n\n"
        f"SPECIFICATION:\n{prompt}\n\n"
        "You must:\n"
        f"1. Write {language} code in {ctx['source_root']}/\n"
        f"2. Write equivalent Lean definitions in spec/Spec/{ctx['name']}/Main.lean\n"
        "3. Write test harnesses (gen_inputs.py, harness.c, Harness.lean)\n"
        "4. Run differential tests until they pass\n"
        "5. Call submit_stage when complete\n\n"
        "REMEMBER: Think in Lean first! Design your data structures and functions\n"
        "so they translate naturally to Lean 4.\n\n"
        "BEGIN: Start by designing the core data structures."
    )


def _build_legacy_payload(ctx: dict) -> str:
    """Build the user payload for legacy translation mode."""
    src_files = sorted(ctx["src_to_lean"].keys())
    lean_files = sorted([p for p in ctx["allowed_lean_writes"] 
                        if p.startswith(f"{ctx['name']}/") and not p.endswith("Verif.lean")])
    
    # Read existing source files for context
    src_blobs = []
    for rel in src_files[:10]:
        p = ctx["source_root"] / rel
        if p.exists():
            content = _read_text_file(p)
            src_blobs.append(f"FILE: {rel}\n{trunc(content, 4000)}\n")

    return (
        "TASK: TRANSLATE existing C code to Lean\n\n"
        "You are translating a safety-critical system. Your job is to:\n"
        "1. Read and understand each source file\n"
        "2. Write a functionally equivalent Lean translation\n"
        "3. Write test harnesses to verify equivalence\n"
        "4. Run differential tests and fix any mismatches\n\n"
        f"SOURCE FILES TO TRANSLATE ({len(src_files)}):\n"
        + "\n".join(_limit_lines(src_files, 30)) + "\n\n"
        f"TARGET LEAN FILES ({len(lean_files)}):\n"
        + "\n".join(_limit_lines(lean_files, 30)) + "\n\n"
        "SOURCE FILE CONTENTS:\n"
        + "\n\n".join(src_blobs) + "\n\n"
        "BEGIN: Start by reading the first source file and translating it."
    )


def run_stage_cogeneration(ctx: dict) -> None:
    """
    Run the Co-Generation stage.
    
    Two modes:
    - Prompt Mode: Generate implementation + Lean from natural language prompt
    - Legacy Mode: Translate existing C to Lean
    
    Success criteria:
    - Code exists in both languages
    - Differential tests pass with 5 runs x 5 cases
    - Lake build succeeds
    """
    log("=== Stage 1: Co-Generation ===")
    ctx["current_stage"] = "COGENERATION"
    
    is_prompt_mode = ctx.get("prompt") is not None

    if is_prompt_mode:
        log(f"Mode: Prompt-driven generation ({ctx.get('language', 'c')})")
        instructions = base_instructions_prompt_cogen(ctx)
        user_payload = _build_prompt_payload(ctx)
    else:
        log("Mode: Legacy translation")
        instructions = base_instructions_cogen(ctx)
        user_payload = _build_legacy_payload(ctx)

    ok = _session_cogeneration(ctx, instructions=instructions, user_payload=user_payload)
    if not ok:
        raise RuntimeError("Co-generation stage did not complete successfully.")

    # Verify final state
    out = run_lake_build(ctx["spec_pkg_root"])
    if not out.startswith("Build Success"):
        raise RuntimeError(f"Co-generation ended but build fails: {out}")

    # Check equivalence state
    if ctx["equiv_state"].get("last_status") != "success":
        raise RuntimeError("Co-generation ended without passing differential tests.")
    if ctx["equiv_state"].get("passed_runs", 0) < DIFF_REQUIRED_RUNS:
        raise RuntimeError(f"Insufficient test runs: {ctx['equiv_state'].get('passed_runs', 0)} < {DIFF_REQUIRED_RUNS}")

    log("=== Stage 1 Complete: Co-Generation successful ===")

