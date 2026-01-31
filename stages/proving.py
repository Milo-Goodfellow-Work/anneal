"""Stage 2: Proving - Submit Lean definitions to Aristotle for spec generation + proofs."""
from __future__ import annotations
import os, asyncio
from helpers import log, run_lake_build, SPEC_DIR, SPEC_SRC_DIR

try:
    import aristotlelib
    from aristotlelib import ProjectInputType
except ImportError:
    aristotlelib = None
    ProjectInputType = None

def run_stage_proving(ctx: dict) -> None:
    log("=== Stage 2: Proving via Aristotle ===")

    if aristotlelib is None:
        log("WARNING: aristotlelib not installed, creating placeholder Verif.lean")
        _create_placeholder_verif()
        return

    api_key = ctx["secrets"]["secrets"].get("ARISTOTLE_API_KEY", "") or os.environ.get("ARISTOTLE_API_KEY", "")
    if not api_key:
        log("WARNING: ARISTOTLE_API_KEY not set, creating placeholder Verif.lean")
        _create_placeholder_verif()
        return

    os.environ["ARISTOTLE_API_KEY"] = api_key

    # Find implementation files (Main.lean and any Module*.lean)
    impl_files = [f for f in SPEC_SRC_DIR.glob("*.lean") 
                  if f.name not in {"Prelude.lean", "Verif.lean"}]
    
    if not impl_files:
        log("No implementation files found")
        _create_placeholder_verif()
        return

    try:
        cwd = os.getcwd()
        os.chdir(SPEC_DIR)
        submission_result = asyncio.run(_submit_to_aristotle(impl_files))
        os.chdir(cwd)
    except Exception as e:
        log(f"Aristotle error: {e}")
        _create_placeholder_verif()

    try:
        from stages.report import generate_report
        generate_report(ctx)
    except Exception:
        pass

    log("=== Stage 2 Complete ===")
    return submission_result if 'submission_result' in locals() else None

async def _submit_to_aristotle(impl_files: list) -> None:
    verif_path = SPEC_SRC_DIR / "Verif.lean"
    
    stub = """import Src.Prelude
import Src.Main

namespace Src
#check @Nat.add
end Src
"""
    verif_path.write_text(stub)
    
    if not run_lake_build(SPEC_DIR).startswith("Build Success"):
        return

    main_content = impl_files[0].read_text() if impl_files else ""
    desc_path = SPEC_DIR / "aristotle_request.txt"
    desc_path.write_text(f"Generate theorems for Src.Main.\n\n```lean\n{main_content}\n```")
    
    verif_rel = str(verif_path.relative_to(SPEC_DIR))
    result = await aristotlelib.Project.prove_from_file(
        input_file_path=str(desc_path.relative_to(SPEC_DIR)),
        project_input_type=ProjectInputType.INFORMAL,
        formal_input_context=verif_rel,
        auto_add_imports=True,
        validate_lean_project=True,
        wait_for_completion=False,
    )
    if result:
        log(f"Aristotle job submitted: {result}")
    return result

def _create_placeholder_verif() -> None:
    path = SPEC_SRC_DIR / "Verif.lean"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""import Src.Prelude
import Src.Main

namespace Src
-- Placeholder: Aristotle not available
end Src
""")
