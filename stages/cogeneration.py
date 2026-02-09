"""Stage 1: Co-Generation - Generate C implementation + Lean from prompt."""
from __future__ import annotations
from typing import List
from helpers import log, run_lake_build, SPEC_DIR
from stages.llm import responses_create, execute_tool_call
from stages.prompts import base_instructions_prompt_cogen
from stages.diff_test import run_differential_test_impl

MAX_TURNS = 64

def run_stage_cogeneration(ctx: dict) -> None:
    """Run co-generation: generate implementation + Lean from prompt."""
    log("=== Stage 1: Co-Generation ===")
    
    prompt = ctx["prompt"]
    # 1. SETUP: Prepare system instructions
    # We load the "Persona" (e.g. "You are an expert C programmer...")
    # and the specific goal for this run.
    instructions = base_instructions_prompt_cogen(prompt)
    payload = (
        f"TASK: Generate a C implementation AND equivalent Lean code\n\n"
        f"SPECIFICATION:\n{prompt}\n\n"
        f"Write C code in generated/, Lean in spec/Src/Main.lean.\n"
        f"Include test harnesses. Run differential tests until they pass, then call submit_stage.\n"
    )
    
    # 2. RUN SESSION: Start the agent loop
    # We pass the instruction + initial user payload to the session manager.
    ok = _session(ctx, instructions, payload)
    if not ok:
        raise RuntimeError("Co-generation did not complete")
    
    out = run_lake_build(SPEC_DIR)
    if not out.startswith("Build Success"):
        raise RuntimeError(f"Build fails after co-generation: {out}")
    
    if ctx["equiv_state"]["last_status"] != "success":
        raise RuntimeError("Co-generation ended without passing differential tests")
    
    log("=== Stage 1 Complete ===")

def _session(ctx: dict, instructions: str, user_payload: str) -> bool:
    from google.genai import types
    
    history: List[types.Content] = [types.Content(role="user", parts=[types.Part.from_text(text=user_payload)])]
    
    for turn in range(MAX_TURNS):
        # ---------------------------------------------------------------------
        # 3. GENERATE: Call the LLM
        # ---------------------------------------------------------------------
        # We send the entire conversation history (user inputs + tool outputs)
        # to the model and ask for the next move.
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
            # -----------------------------------------------------------------
            # 4. EXECUTE TOOL: Run the requested action
            # -----------------------------------------------------------------
            # The model asked to run a tool (e.g. write_file, run_differential_test).
            # We execute it locally and get the result (stdout/stderr).
            log(f"  Call: {call.name}({{{', '.join(f'{k}: <{len(str(v))} chars>' if len(str(v)) > 50 else f'{k}: {v!r}' for k,v in (call.args or {}).items())}}})")
            out_item, ok = execute_tool_call(ctx, call, run_differential_test_impl)
            result_preview = out_item.get("output", "")[:200]
            if call.name == "run_differential_test":
                log(f"  [DiffTest] {result_preview}")
            parts.append(types.Part.from_function_response(name=call.name, response={"result": out_item.get("output", "")}))
            if call.name == "submit_stage" and ok:
                submit_ok = True
        
        # ---------------------------------------------------------------------
        # 5. FEEDBACK: Append tool outputs to history
        # ---------------------------------------------------------------------
        # We treat the tool output as a message from role="tool".
        # The model sees this in the next turn and decides if it fixed the issue.
        history.append(types.Content(role="tool", parts=parts))
        
        if submit_ok:
            return True
    
    return False
