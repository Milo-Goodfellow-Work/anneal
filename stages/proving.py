"""Stage 2: Proving - Submit Lean definitions to Aristotle for spec generation + proofs."""
from __future__ import annotations
import os, asyncio
from pathlib import Path
from typing import Optional
from helpers import log, run_lake_build

try:
    import aristotlelib
    from aristotlelib import ProjectInputType
except ImportError:
    aristotlelib = None
    ProjectInputType = None

def run_stage_proving(ctx: dict) -> None:
    log("=== Stage 2: Proving via Aristotle ===")
    ctx["current_stage"] = "PROVING"

    if aristotlelib is None:
        log("WARNING: aristotlelib not installed, creating placeholder Verif.lean")
        _create_placeholder_verif(ctx)
        return

    api_key = ctx["secrets"]["secrets"].get("ARISTOTLE_API_KEY", "") or os.environ.get("ARISTOTLE_API_KEY", "")
    if not api_key:
        log("WARNING: ARISTOTLE_API_KEY not set, creating placeholder Verif.lean")
        _create_placeholder_verif(ctx)
        return

    os.environ["ARISTOTLE_API_KEY"] = api_key

    impl_files = [ctx["spec_src_root"] / rel for rel in sorted(ctx["allowed_lean_writes"])
                  if not rel.endswith("Verif.lean") and (ctx["spec_src_root"] / rel).exists()]

    if not impl_files:
        log("No implementation files found")
        _create_placeholder_verif(ctx)
        return

    try:
        cwd = os.getcwd()
        os.chdir(ctx["spec_pkg_root"])
        asyncio.run(_submit_to_aristotle(ctx, impl_files))
        os.chdir(cwd)
    except Exception as e:
        log(f"Aristotle error: {e}")
        _create_placeholder_verif(ctx)

    try:
        from stages.report import generate_report
        generate_report(ctx)
    except Exception:
        pass

    log("=== Stage 2 Complete ===")

async def _submit_to_aristotle(ctx: dict, impl_files: list) -> None:
    verif_path = ctx["spec_src_root"] / "Verif.lean"
    
    stub = """import Src.Prelude
import Src.Main

namespace Src
#check @Nat.add
end Src
"""
    verif_path.write_text(stub)
    
    if not run_lake_build(ctx["spec_pkg_root"]).startswith("Build Success"):
        return

    main_content = impl_files[0].read_text() if impl_files else ""
    desc_path = ctx["spec_pkg_root"] / "aristotle_request.txt"
    desc_path.write_text(f"Generate theorems for Src.Main.\n\n```lean\n{main_content}\n```")
    
    verif_rel = str(verif_path.relative_to(ctx["spec_pkg_root"]))
    result = await aristotlelib.Project.prove_from_file(
        input_file_path=str(desc_path.relative_to(ctx["spec_pkg_root"])),
        project_input_type=ProjectInputType.INFORMAL,
        formal_input_context=verif_rel,
        auto_add_imports=True,
        validate_lean_project=True,
        wait_for_completion=False,
    )
    if result:
        log(f"Aristotle job submitted: {result}")

def _create_placeholder_verif(ctx: dict) -> None:
    path = ctx["spec_src_root"] / "Verif.lean"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""import Src.Prelude
import Src.Main

namespace Src
-- Placeholder: Aristotle not available
end Src
""")
