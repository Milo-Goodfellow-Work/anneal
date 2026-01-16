"""
Anneal Stages - Translation stage implementation.

This stage translates source code files to Lean 4.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..processor import ProjectProcessor

from ..helpers import (
    log, run_lake_build,
)


def run_stage_translation(proc: "ProjectProcessor", restart_reason: Optional[str] = None) -> None:
    """Run the Translation stage - convert source files to Lean."""
    log("--- Stage: Translation ---")
    proc._current_stage = "TRANSLATION"

    if restart_reason:
        log(f"[RESTART] Previous translation failed due to: {restart_reason[:200]}...")

    project_summary = proc._project_summary()
    if restart_reason:
        # Inject the restart reason into the project summary so model sees it
        project_summary = (
            f"!!! IMPORTANT: A previous translation attempt failed during differential testing !!!\n"
            f"Failure reason: {restart_reason}\n\n"
            f"Pay close attention to faithfully matching the C semantics, especially:\n"
            f"- Free-list ordering (LIFO stack behavior)\n"
            f"- Pointer/index identity across operations\n"
            f"- Numeric parsing (strtoul-like behavior)\n"
            f"- Edge cases in allocator exhaustion\n\n"
            + project_summary
        )
    log("Project summary computed.")

    # Translate each source file to its target, then repair until that module builds.
    # After each file converges locally, do a full `lake build` and do not move on until the full project builds.
    for src_rel, out_rel in sorted(proc.src_to_lean.items()):
        log(f"Translating {src_rel} -> {out_rel}")

        ok = proc._translate_file(project_summary=project_summary, src_rel=src_rel, out_rel=out_rel)
        if not ok:
            raise RuntimeError(f"Translation session failed for {src_rel}")

        ok = proc._repair_file_until_builds(project_summary=project_summary, src_rel=src_rel, out_rel=out_rel)
        if not ok:
            raise RuntimeError(f"Failed to converge {out_rel} to a compiling state")

        # Full project build check after each file
        log("Full-project build check (after per-file convergence)...")
        proc._repair_project_until_builds(project_summary=project_summary)
        log("Full-project build OK. Proceeding to next file.")

    # Final full build (sanity check).
    out = run_lake_build(proc.spec_pkg_root)
    if not out.startswith("Build Success"):
        raise RuntimeError("Translation complete but lake build still fails (should not happen).")

    log("Translation complete: lake build succeeded.")
