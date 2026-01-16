"""
Anneal Stages - Verification stage implementation.

This stage submits Verif.lean to Aristotle for formal verification.
"""
from __future__ import annotations
import os
import asyncio

from helpers import log, run_lake_build

try:
    import aristotlelib
except ImportError:
    aristotlelib = None


def run_stage_verification(ctx: dict) -> None:
    """Run the Verification stage - submit to Aristotle for formal proof."""
    target_file = ctx["spec_project_root"] / "Verif.lean"
    if not target_file.exists():
        log("No Verif.lean found. Skipping Aristotle.")
        return
    if not aristotlelib:
        log("aristotlelib missing. Skipping Aristotle.")
        return

    log("=== Aristotle Verification ===")
    os.environ["ARISTOTLE_API_KEY"] = ctx["secrets"]["secrets"].get("ARISTOTLE_API_KEY", "")

    try:
        cwd = os.getcwd()
        os.chdir(ctx["spec_pkg_root"])

        rel_target = target_file.relative_to(ctx["spec_pkg_root"])
        log(f"Submitting {rel_target} to Aristotle...")

        result = asyncio.run(
            aristotlelib.Project.prove_from_file(
                input_file_path=str(rel_target),
                auto_add_imports=True,
                validate_lean_project=True,
                wait_for_completion=True,
            )
        )

        os.chdir(cwd)
        log(f"Aristotle Output: {result}")

        res_path = ctx["spec_pkg_root"] / result
        if res_path.exists():
            res_path.rename(target_file)
            log("Verified spec saved over Verif.lean.")
            bres = run_lake_build(ctx["spec_pkg_root"])
            log(f"Final Build: {bres}")

    except Exception as e:
        log(f"Aristotle Error: {e}")
        try:
            os.chdir(cwd)
        except Exception:
            pass
