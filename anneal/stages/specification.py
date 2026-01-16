"""
Anneal Stages - Specification stage implementation.

This stage writes formal specifications in Verif.lean.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..processor import ProjectProcessor

from ..helpers import (
    log, trunc, run_lake_build, parse_lean_errors,
    _read_text_file, _limit_lines, MAX_SESSION_TURNS,
)


def run_stage_specification(proc: "ProjectProcessor") -> None:
    """Run the Specification stage - write Verif.lean with formal specs."""
    log("--- Stage: Specification ---")
    proc._current_stage = "SPECIFICATION"

    out_rel = f"{proc.name}/Verif.lean"
    src_list = "\n".join(_limit_lines(sorted(proc.src_to_lean.keys()), 120))
    lean_list = "\n".join(_limit_lines(sorted([p for p in proc.allowed_lean_writes if p.startswith(f"{proc.name}/")]), 160))

    sample_files = _limit_lines(sorted([p for p in proc.allowed_lean_writes if p.startswith(f"{proc.name}/") and p.endswith(".lean")]), 6)
    sample_blob = []
    for rel in sample_files:
        p = proc.spec_src_root / rel
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

    ok = proc._session_until_successful_write(
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
        out = run_lake_build(proc.spec_pkg_root)
        if out.startswith("Build Success"):
            break
        log(f"Spec repair step {repair_step + 1}: build failed, asking model to fix Verif.lean")

        errs = parse_lean_errors(out, max_n=6)
        err_lines = "\n".join([f"{e.file}:{e.line}:{e.col}: {e.msg}" for e in errs])
        verif_content = _read_text_file(proc.spec_src_root / out_rel) if (proc.spec_src_root / out_rel).exists() else ""

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

        repair_ok = proc._session_until_successful_write(
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
