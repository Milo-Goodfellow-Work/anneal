"""
Anneal Stages - Translation stage implementation.

This stage translates source code files to Lean 4.
"""
from __future__ import annotations
import json
from typing import Optional, List, Dict, Any
from pathlib import Path

from helpers import (
    log, trunc, _read_text_file, run_lake_build, run_lake_build_target,
    module_name_from_lean_path, parse_lean_errors, excerpt_around,
    MAX_SESSION_TURNS, MAX_REPAIR_TURNS_PER_FILE, MAX_REPAIR_TURNS_GLOBAL,
)
from stages.llm import responses_create, execute_tool_call, RestartTranslationError
from stages.prompts import base_instructions, project_summary


def _run_differential_test_impl(ctx: dict, args: dict) -> str:
    """Placeholder for differential test - will be implemented in equivalence."""
    return json.dumps({"status": "error", "message": "Differential tests not available in translation stage"})


def _session_until_successful_write(
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
                "You MUST call tools to modify files or verifying builds.\n"
                "If you are finished or stuck, explain why, but you must attempt a tool call first.\n"
            )
            continue

        tool_outputs: List[Dict[str, Any]] = []
        wrote_ok = False

        for call in tool_calls:
            out_item, ok = execute_tool_call(ctx, call, _run_differential_test_impl)
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


def _translate_file(ctx: dict, *, project_summary_text: str, src_rel: str, out_rel: str) -> bool:
    """Translate a single source file."""
    src_txt = _read_text_file(ctx["source_root"] / src_rel)
    existing = _read_text_file(ctx["spec_src_root"] / out_rel) if (ctx["spec_src_root"] / out_rel).exists() else ""

    user_payload = (
        "TASK: Translate the given source file into the target Lean file.\n"
        "You may call read_source_file / read_lean_file if needed.\n"
        "You MUST call write_lean_file to fully overwrite the target Lean file.\n\n"
        "PROJECT SUMMARY:\n"
        f"{project_summary_text}\n\n"
        f"SOURCE FILE: {src_rel}\n"
        "----- BEGIN SOURCE CONTENT -----\n"
        f"{src_txt}\n"
        "----- END SOURCE CONTENT -----\n\n"
        f"TARGET LEAN FILE: {out_rel}\n"
        "----- BEGIN CURRENT TARGET CONTENT -----\n"
        f"{trunc(existing, 6500)}\n"
        "----- END CURRENT TARGET CONTENT -----\n\n"
        "REQUIREMENTS:\n"
        f"- The Lean file MUST be in namespace Spec.{ctx['name']}\n"
        "- It MUST import Spec.Prelude\n"
        "- Implement real semantics; no placeholders or constant returns for integrity checks.\n"
        "- Keep deterministic behavior.\n"
    )

    ok = _session_until_successful_write(
        ctx,
        stage="TRANSLATION",
        focus_src=src_rel,
        focus_out=out_rel,
        user_payload=user_payload,
        max_turns=MAX_SESSION_TURNS,
    )
    return ok


def _repair_file_until_builds(ctx: dict, *, project_summary_text: str, src_rel: str, out_rel: str) -> bool:
    """Repair a file until it builds."""
    target_mod = module_name_from_lean_path(out_rel)
    if not target_mod:
        log(f"Cannot compute module name for {out_rel}")
        return False

    out = run_lake_build_target(ctx["spec_pkg_root"], target=target_mod)
    if out.startswith("Build Success"):
        return True

    for step in range(MAX_REPAIR_TURNS_PER_FILE):
        errs = parse_lean_errors(out, max_n=6)
        p = ctx["spec_src_root"] / out_rel
        cur = _read_text_file(p) if p.exists() else ""

        if errs:
            e0 = errs[0]
            snippet = excerpt_around(cur, e0.line, radius=16)
            err_lines = "\n".join([f"{e.file}:{e.line}:{e.col}: {e.msg}" for e in errs])
        else:
            snippet = trunc(cur, 1400)
            err_lines = trunc(out, 2200)

        src_txt = _read_text_file(ctx["source_root"] / src_rel)

        user_payload = (
            "TASK: Fix the target Lean file so that it compiles, WITHOUT changing intended semantics.\n"
            "You MUST edit ONLY the target Lean file.\n"
            "You may read other files if necessary, but the final action must be write_lean_file on the target.\n\n"
            "PROJECT SUMMARY:\n"
            f"{project_summary_text}\n\n"
            f"SOURCE FILE (truth): {src_rel}\n"
            "----- BEGIN SOURCE CONTENT -----\n"
            f"{trunc(src_txt, 7500)}\n"
            "----- END SOURCE CONTENT -----\n\n"
            f"TARGET LEAN FILE: {out_rel}\n"
            "----- BEGIN CURRENT TARGET CONTENT (truncated) -----\n"
            f"{trunc(cur, 7500)}\n"
            "----- END CURRENT TARGET CONTENT -----\n\n"
            "BUILD ERRORS (focus on the FIRST one):\n"
            f"{trunc(err_lines, 2600)}\n\n"
            "SNIPPET AROUND FIRST ERROR:\n"
            f"{snippet}\n\n"
            "REPAIR RULES:\n"
            "- Fix the FIRST error with the smallest correct change.\n"
            "- Keep import Spec.Prelude only.\n"
            f"- Keep namespace Spec.{ctx['name']}.\n"
            "- Do not introduce placeholders/stubs.\n"
        )

        ok = _session_until_successful_write(
            ctx,
            stage=f"REPAIR (file) step {step+1}",
            focus_src=src_rel,
            focus_out=out_rel,
            user_payload=user_payload,
            max_turns=MAX_SESSION_TURNS,
        )
        if not ok:
            log("Repair session stalled.")
            return False

        out = run_lake_build_target(ctx["spec_pkg_root"], target=target_mod)
        log(trunc(out, 1800))
        if out.startswith("Build Success"):
            return True

    return False


def _repair_project_until_builds(ctx: dict, *, project_summary_text: str) -> None:
    """Repair the project until all files build."""
    from helpers import module_to_spec_relpath, extract_failed_import_module
    
    for step in range(MAX_REPAIR_TURNS_GLOBAL):
        out = run_lake_build(ctx["spec_pkg_root"])
        if out.startswith("Build Success"):
            return

        errs = parse_lean_errors(out, max_n=1)
        if not errs:
            # Try to extract failed module from output
            failed_mod = extract_failed_import_module(out)
            if failed_mod:
                rel = module_to_spec_relpath(failed_mod)
                if rel and rel in ctx["allowed_lean_writes"]:
                    src_rel = ctx["lean_to_src"].get(rel)
                    if src_rel:
                        log(f"Global repair: targeting missing module {rel}")
                        _repair_file_until_builds(ctx, project_summary_text=project_summary_text, src_rel=src_rel, out_rel=rel)
                        continue
            raise RuntimeError(f"Global repair stuck: no actionable error. Build output:\n{trunc(out, 2000)}")

        e = errs[0]
        file_path = Path(e.file)
        
        # Find rel path under spec_src_root
        try:
            rel = str(file_path.relative_to(ctx["spec_src_root"])).replace("\\", "/")
        except ValueError:
            raise RuntimeError(f"Error in file not under spec_src_root: {e.file}")

        if rel in ctx["locked_lean_paths"]:
            # Locked file error - try to find underlying cause
            failed_mod = extract_failed_import_module(e.msg)
            if failed_mod:
                inner_rel = module_to_spec_relpath(failed_mod)
                if inner_rel and inner_rel in ctx["allowed_lean_writes"]:
                    rel = inner_rel

        if rel not in ctx["allowed_lean_writes"]:
            raise RuntimeError(f"Cannot repair locked file: {rel}")

        src_rel = ctx["lean_to_src"].get(rel)
        if not src_rel:
            raise RuntimeError(f"No source mapping for {rel}")

        log(f"Global repair step {step+1}: fixing {rel}")
        ok = _repair_file_until_builds(ctx, project_summary_text=project_summary_text, src_rel=src_rel, out_rel=rel)
        if not ok:
            raise RuntimeError(f"Failed to repair {rel}")

    raise RuntimeError("Global repair exceeded max steps; refusing to proceed.")


def run_stage_translation(ctx: dict, restart_reason: Optional[str] = None) -> None:
    """Run the Translation stage - convert source files to Lean."""
    log("--- Stage: Translation ---")
    ctx["current_stage"] = "TRANSLATION"

    if restart_reason:
        log(f"[RESTART] Previous translation failed due to: {restart_reason[:200]}...")

    summary = project_summary(ctx)
    if restart_reason:
        summary = (
            f"!!! IMPORTANT: A previous translation attempt failed during differential testing !!!\n"
            f"Failure reason: {restart_reason}\n\n"
            f"Pay close attention to faithfully matching the C semantics, especially:\n"
            f"- Free-list ordering (LIFO stack behavior)\n"
            f"- Pointer/index identity across operations\n"
            f"- Numeric parsing (strtoul-like behavior)\n"
            f"- Edge cases in allocator exhaustion\n\n"
            + summary
        )
    log("Project summary computed.")

    for src_rel, out_rel in sorted(ctx["src_to_lean"].items()):
        log(f"Translating {src_rel} -> {out_rel}")

        ok = _translate_file(ctx, project_summary_text=summary, src_rel=src_rel, out_rel=out_rel)
        if not ok:
            raise RuntimeError(f"Translation session failed for {src_rel}")

        ok = _repair_file_until_builds(ctx, project_summary_text=summary, src_rel=src_rel, out_rel=out_rel)
        if not ok:
            raise RuntimeError(f"Failed to converge {out_rel} to a compiling state")

        log("Full-project build check (after per-file convergence)...")
        _repair_project_until_builds(ctx, project_summary_text=summary)
        log("Full-project build OK. Proceeding to next file.")

    out = run_lake_build(ctx["spec_pkg_root"])
    if not out.startswith("Build Success"):
        raise RuntimeError("Translation complete but lake build still fails (should not happen).")

    log("Translation complete: lake build succeeded.")
