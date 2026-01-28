"""Stage 1: Co-Generation - Generate C implementation + Lean from prompt."""
from __future__ import annotations
from typing import List
from helpers import log, run_lake_build, SPEC_DIR, DIFF_REQUIRED_RUNS
from stages.llm import responses_create, execute_tool_call
from stages.prompts import base_instructions_prompt_cogen
from stages.diff_test import run_differential_test_impl

MAX_TURNS = 64

def run_stage_cogeneration(ctx: dict) -> None:
    """Run co-generation: generate implementation + Lean from prompt."""
    log("=== Stage 1: Co-Generation ===")
    
    prompt = ctx.get("prompt", "No prompt provided")
    instructions = base_instructions_prompt_cogen(prompt)
    payload = (
        f"TASK: Generate a C implementation AND equivalent Lean code\n\n"
        f"SPECIFICATION:\n{prompt}\n\n"
        f"Write C code in generated/, Lean in spec/Src/Main.lean.\n"
        f"Include test harnesses. Run differential tests until they pass, then call submit_stage.\n"
    )
    
    ok = _session(ctx, instructions, payload)
    if not ok:
        raise RuntimeError("Co-generation did not complete")
    
    out = run_lake_build(SPEC_DIR)
    if not out.startswith("Build Success"):
        raise RuntimeError(f"Build fails after co-generation: {out}")
    
    if ctx["equiv_state"].get("last_status") != "success":
        raise RuntimeError("Co-generation ended without passing differential tests")
    if ctx["equiv_state"].get("passed_runs", 0) < DIFF_REQUIRED_RUNS:
        raise RuntimeError(f"Insufficient test runs: {ctx['equiv_state'].get('passed_runs', 0)} < {DIFF_REQUIRED_RUNS}")
    
    log("=== Stage 1 Complete ===")

def _session(ctx: dict, instructions: str, user_payload: str) -> bool:
    from google.genai import types
    
    history: List[types.Content] = [types.Content(role="user", parts=[types.Part.from_text(text=user_payload)])]
    
    for turn in range(MAX_TURNS):
        resp = responses_create(ctx, instructions=instructions, input_data=history)
        model_content = resp.candidates[0].content if hasattr(resp, 'candidates') and resp.candidates else None
        tool_calls = list(resp.function_calls) if hasattr(resp, 'function_calls') and resp.function_calls else []
        
        log(f"[Turn {turn+1}] {len(tool_calls)} calls: {[c.name for c in tool_calls]}")
        
        if not tool_calls:
            if model_content:
                history.append(model_content)
            history.append(types.Content(role="user", parts=[types.Part.from_text(
                text="NO TOOL CALLS. You MUST call tools to make progress.")]))
            continue
        
        if model_content:
            history.append(model_content)
        
        parts: List[types.Part] = []
        submit_ok = False
        
        for call in tool_calls:
            log(f"  Call: {call.name}({{{', '.join(f'{k}: <{len(str(v))} chars>' if len(str(v)) > 50 else f'{k}: {v!r}' for k,v in (call.args or {}).items())}}})")
            out_item, ok = execute_tool_call(ctx, call, run_differential_test_impl)
            result_preview = out_item.get("output", "")[:200]
            if call.name == "run_differential_test":
                log(f"  [DiffTest] {result_preview}")
            parts.append(types.Part.from_function_response(name=call.name, response={"result": out_item.get("output", "")}))
            if call.name == "submit_stage" and ok:
                submit_ok = True
        
        history.append(types.Content(role="tool", parts=parts))
        
        if submit_ok:
            return True
    
    return False
