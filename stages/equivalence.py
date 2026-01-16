"""
Anneal Stages - Equivalence stage implementation.

This stage implements robust differential testing between C and Lean harnesses.
"""
from __future__ import annotations
from typing import Optional, Any, List, Dict

from helpers import (
    log, trunc, run_lake_build, _limit_lines,
    DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN,
)
from stages.llm import responses_create, execute_tool_call
from stages.prompts import base_instructions
from stages.diff_test import run_differential_test_impl


def run_stage_equivalence(ctx: dict) -> None:
    """Run the Equivalence stage - differential testing between C and Lean."""
    log("--- Stage: Equivalence ---")
    ctx["current_stage"] = "EQUIVALENCE"

    project_files = sorted([p for p in ctx["allowed_lean_writes"] if p.startswith(f"{ctx['name']}/")])
    instructions = base_instructions(ctx, stage="EQUIVALENCE")

    brief = (
        "TASK: Implement ROBUST differential testing in a safety-critical setting.\n"
        "You must implement these writable files:\n"
        f"- {ctx['safety_case_rel']} (NOT in this stage; that's hardening)\n"
        "- spec/tests/gen_inputs.py\n"
        "- spec/tests/harness.c\n"
        "- tests/Harness.lean (under spec/Spec/)\n\n"
        "Generator contract (MANDATORY):\n"
        "- gen_inputs.py must accept: --seed INT --n INT\n"
        "- It must print >= n non-empty command lines.\n"
        "- It must generate diverse and adversarial sequences of operations (random + edge cases).\n\n"
        "Harness contract (MANDATORY):\n"
        "- Both harnesses must parse the exact same command language.\n"
        "- Both must print deterministic stdout for each command.\n"
        "- Keep it fast; avoid slow per-line Lean IO patterns.\n"
        "- C harness: use standard C11. For strtok_r, add '#define _POSIX_C_SOURCE 200809L' before <string.h>.\n"
        "- C harness: do NOT #include .c files directly. Only #include headers; linker provides implementations.\n"
        "- Lean harness: The 'main' function MUST be visible to 'lean --run'. Either:\n"
        "  (a) define 'def main' OUTSIDE any namespace, or\n"
        "  (b) annotate with '@[main] def main' inside a namespace.\n"
        "  If you get 'unknown declaration main', you probably have it inside a namespace without @[main].\n\n"
        "Testing requirement (MANDATORY):\n"
        f"- You MUST call run_differential_test until it returns JSON status=success with passed_runs={DIFF_REQUIRED_RUNS}.\n"
        f"- Each run must have >= {DIFF_MIN_CASES_PER_RUN} cases.\n"
        "- If you get timeouts or diffs, fix the problem and rerun.\n"
        "- If the C harness crashes, treat it as a bug in generator/harness input validation or in the source engine; do NOT call restart_translation unless you have a confirmed semantic mismatch (status=diff).\n"
        "- You may edit translated Lean files to correct semantic mismatches.\n\n"
        "Note: you cannot finish this stage by calling submit_stage unless tests pass.\n\n"
        "Translated project Lean files:\n"
        + "\n".join(_limit_lines(project_files, 120))
    )

    previous_response_id: Optional[str] = None
    current_input: Any = brief

    for turn in range(60):
        log(f"Turn {turn+1}")
        resp = responses_create(
            ctx,
            instructions=instructions,
            input_data=current_input,
            previous_response_id=previous_response_id,
            tool_choice=None,
            parallel_tool_calls=False,
        )
        previous_response_id = resp.id

        tool_calls = []
        if getattr(resp, "output", None):
            for item in resp.output:
                if item.type == "message":
                    for part in item.content:
                        if part.type == "output_text":
                            log(f"Model: {trunc(part.text)}")
                elif item.type == "function_call":
                    tool_calls.append(item)

        if not tool_calls:
            current_input = (
                "NO TOOL CALLS DETECTED.\n"
                "You MUST call at least one tool each turn.\n"
                "Next action: call run_differential_test with:\n"
                "- gen_script_path = spec/tests/gen_inputs.py\n"
                "- c_harness_path = spec/tests/harness.c\n"
                "- lean_harness_path = tests/Harness.lean\n"
                "If it fails, read the failing file(s), fix, and retry.\n"
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
            break

    out = run_lake_build(ctx["spec_pkg_root"])
    if not out.startswith("Build Success"):
        raise RuntimeError("Equivalence ended but build fails.")

    if ctx["equiv_state"].get("last_status") != "success" or ctx["equiv_state"].get("passed_runs", 0) < DIFF_REQUIRED_RUNS:
        raise RuntimeError("Equivalence ended without robust passing differential tests (should not happen due to gating).")

    log("Equivalence complete: robust differential tests passed.")
