"""
Anneal Stages - Specification stage implementation.

This stage writes formal specifications in Verif.lean.
"""
from __future__ import annotations
import json
from typing import Optional, Any, List, Dict

from helpers import (
    log, trunc, run_lake_build, parse_lean_errors,
    _read_text_file, _limit_lines, MAX_SESSION_TURNS,
)
from stages.llm import responses_create, execute_tool_call
from stages.prompts import base_instructions
from stages.diff_test import run_differential_test_impl


def _session_until_successful_write_spec(
    ctx: dict,
    *,
    stage: str,
    focus_src: str,
    focus_out: str,
    user_payload: str,
    max_turns: int = MAX_SESSION_TURNS,
) -> bool:
    """Run a session until the model successfully writes to focus_out."""
    instructions = base_instructions(ctx, stage=stage, focus_src=focus_src, focus_out=focus_out)
    previous_response_id: Optional[str] = None
    current_input: Any = user_payload

    for turn in range(max_turns):
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
            log("No tool calls; nudging model.")
            current_input = (
                "NO TOOL CALLS DETECTED.\n"
                "You MUST call tools to modify files or verify builds.\n"
            )
            continue

        tool_outputs: List[Dict[str, Any]] = []
        wrote_ok = False

        for call in tool_calls:
            out_item, ok = execute_tool_call(ctx, call, run_differential_test_impl)
            tool_outputs.append(out_item)

            if call.name == "write_lean_file":
                try:
                    a = json.loads(call.arguments) if call.arguments else {}
                except json.JSONDecodeError:
                    a = {}
                path = (a.get("path", "") or "").replace("\\", "/")
                if ok and path == focus_out:
                    wrote_ok = True

        current_input = tool_outputs

        if wrote_ok:
            return True

    log("Session exceeded max turns without a successful write to the focus file.")
    return False


def run_stage_specification(ctx: dict) -> None:
    """Run the Specification stage - write Verif.lean with formal specs."""
    log("--- Stage: Specification ---")
    ctx["current_stage"] = "SPECIFICATION"

    out_rel = f"{ctx['name']}/Verif.lean"
    src_list = "\n".join(_limit_lines(sorted(ctx["src_to_lean"].keys()), 120))
    lean_list = "\n".join(_limit_lines(sorted([p for p in ctx["allowed_lean_writes"] if p.startswith(f"{ctx['name']}/")]), 160))

    sample_files = _limit_lines(sorted([p for p in ctx["allowed_lean_writes"] if p.startswith(f"{ctx['name']}/") and p.endswith(".lean")]), 6)
    sample_blob = []
    for rel in sample_files:
        p = ctx["spec_src_root"] / rel
        if p.exists():
            sample_blob.append(f"FILE: {rel}\n" + trunc(_read_text_file(p), 2800) + "\n")

    user_payload = (
        "TASK: Write a SPECIFICATION for the translated project.\n"
        "This is SAFETY-CRITICAL: the spec must be meaningful, not generic.\n"
        "Proofs may use sorry here, but statements must connect to the translated definitions.\n"
        "IMPORTANT: Verif.lean is proofs-only (anti-smuggling): do NOT introduce def/abbrev/instance/axiom/etc.\n\n"
        f"TARGET: {out_rel}\n\n"
        "REQUIREMENTS:\n"
        "- Include at least 10 non-trivial theorems/lemmas.\n"
        "- Include invariants about memory safety / bounds (arrays/pools), functional correctness conditions, and determinism.\n"
        "- Include at least 2 theorems that connect a multi-step scenario to postconditions.\n"
        "- Make sure the file parses and typechecks.\n\n"
        "SOURCE FILES:\n"
        f"{src_list}\n\n"
        "TRANSLATED LEAN FILES:\n"
        f"{lean_list}\n\n"
        "SAMPLE LEAN CONTENT:\n"
        + "\n\n".join(sample_blob)
    )

    ok = _session_until_successful_write_spec(
        ctx,
        stage="SPECIFICATION",
        focus_src="(project)",
        focus_out=out_rel,
        user_payload=user_payload,
        max_turns=MAX_SESSION_TURNS,
    )
    if not ok:
        raise RuntimeError("Specification session stalled.")

    # Repair loop: if Verif.lean broke the build, ask model to fix it
    for repair_step in range(10):
        out = run_lake_build(ctx["spec_pkg_root"])
        if out.startswith("Build Success"):
            break
        log(f"Spec repair step {repair_step + 1}: build failed, asking model to fix Verif.lean")

        errs = parse_lean_errors(out, max_n=6)
        err_lines = "\n".join([f"{e.file}:{e.line}:{e.col}: {e.msg}" for e in errs])
        verif_content = _read_text_file(ctx["spec_src_root"] / out_rel) if (ctx["spec_src_root"] / out_rel).exists() else ""

        repair_payload = (
            "TASK: Fix the Verif.lean file so the project builds.\n"
            "The specification you wrote has errors. Fix them while keeping meaningful theorems.\n\n"
            f"TARGET: {out_rel}\n\n"
            "CURRENT CONTENT:\n"
            f"{trunc(verif_content, 8000)}\n\n"
            "BUILD ERRORS:\n"
            f"{trunc(err_lines, 3000)}\n\n"
            "FULL BUILD OUTPUT:\n"
            f"{trunc(out, 3000)}\n"
        )

        repair_ok = _session_until_successful_write_spec(
            ctx,
            stage="SPECIFICATION (repair)",
            focus_src="(project)",
            focus_out=out_rel,
            user_payload=repair_payload,
            max_turns=8,
        )
        if not repair_ok:
            log("Spec repair session stalled; retrying...")
    else:
        raise RuntimeError("Specification stage: Verif.lean could not be repaired after 10 attempts.")

    log("Specification complete: typechecks.")
