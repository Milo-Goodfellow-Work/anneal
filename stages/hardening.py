"""
Anneal Stages - Hardening stage implementation.

This stage writes safety case documentation and improves robustness.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Any, List, Dict

from helpers import (
    log, trunc, run_lake_build, _read_text_file, _limit_lines,
    DIFF_REQUIRED_RUNS,
)
from stages.llm import responses_create, execute_tool_call
from stages.prompts import base_instructions
from stages.diff_test import run_differential_test_impl


def run_stage_hardening(ctx: dict) -> None:
    """Run the Hardening stage - write safety case and improve robustness."""
    log("--- Stage: Hardening (Safety Case + Improvements) ---")
    ctx["current_stage"] = "HARDENING"

    instructions = base_instructions(ctx, stage="HARDENING")

    last_rep = ctx["equiv_state"].get("last_report")
    rep_str = json.dumps(last_rep, indent=2) if isinstance(last_rep, dict) else str(last_rep)

    project_lean_files = sorted([p for p in ctx["allowed_lean_writes"] if p.startswith(f"{ctx['name']}/") and p.endswith(".lean")])
    sample_files = _limit_lines(project_lean_files, 8)
    samples: List[str] = []
    for rel in sample_files:
        p = ctx["spec_src_root"] / rel
        if p.exists():
            samples.append(f"FILE: {rel}\n" + trunc(_read_text_file(p), 2400))

    harness_lean = _read_text_file(ctx["spec_src_root"] / "tests/Harness.lean") if (ctx["spec_src_root"] / "tests/Harness.lean").exists() else ""
    gen_py = _read_text_file(Path("spec/tests/gen_inputs.py")) if Path("spec/tests/gen_inputs.py").exists() else ""
    c_h = _read_text_file(Path("spec/tests/harness.c")) if Path("spec/tests/harness.c").exists() else ""

    payload = (
        "TASK: HARDEN the result for safety-critical confidence.\n\n"
        "Step A (required): Write an expert-facing Safety Case markdown file at:\n"
        f"- {ctx['safety_case_rel']}\n"
        "It must argue (to a formal methods expert) why your translation, differential tests, and spec are robust.\n"
        "It must include:\n"
        "- Explicit claims (translation correctness, test adequacy, harness determinism, spec relevance)\n"
        "- Concrete evidence from the differential test report (seeds, case counts)\n"
        "- Identified weaknesses/risks + mitigation plan\n\n"
        "Step B (required): ACT on the weaknesses you identified.\n"
        "- If tests are weak, improve gen_inputs.py and harnesses.\n"
        "- If translation seems brittle, improve Lean code.\n"
        "- If spec is generic, improve Verif.lean.\n"
        "- After changes, call run_differential_test and ensure success.\n\n"
        "You cannot finish by calling submit_stage unless:\n"
        "- safety case file exists\n"
        "- lake build succeeds\n"
        "- run_differential_test returns status=success with required runs and case counts\n\n"
        "CURRENT TEST REPORT:\n"
        f"{rep_str}\n\n"
        "CURRENT HARNESS FILES (snippets):\n"
        "----- spec/tests/gen_inputs.py -----\n"
        f"{trunc(gen_py, 2500)}\n\n"
        "----- spec/tests/harness.c -----\n"
        f"{trunc(c_h, 2500)}\n\n"
        "----- spec/Spec/tests/Harness.lean -----\n"
        f"{trunc(harness_lean, 3000)}\n\n"
        "SAMPLE PROJECT LEAN FILES:\n"
        + "\n\n".join(samples)
    )

    previous_response_id: Optional[str] = None
    current_input: Any = payload

    for turn in range(80):
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
            raise RuntimeError("Hardening stage stalled: no tool calls.")

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

    if not Path(ctx["safety_case_rel"]).exists():
        raise RuntimeError("Hardening ended but safety case file missing.")

    out = run_lake_build(ctx["spec_pkg_root"])
    if not out.startswith("Build Success"):
        raise RuntimeError("Hardening ended but build fails.")

    if ctx["equiv_state"].get("last_status") != "success" or ctx["equiv_state"].get("passed_runs", 0) < DIFF_REQUIRED_RUNS:
        raise RuntimeError("Hardening ended but robust differential tests not passing.")

    log("Hardening complete: safety case written and outputs improved, tests pass robustly.")
