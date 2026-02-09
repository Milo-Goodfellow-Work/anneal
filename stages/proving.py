"""Stage 2: Proving - Submit Lean definitions to Aristotle for spec generation + proofs."""
# This module coordinates Stage 2: Formal Verification.
# It takes the C-equivalent Lean spec from Stage 1 and submits it 
# to Harmonic's Aristotle prover via the aristotlelib SDK.
from __future__ import annotations
import os, asyncio
from pathlib import Path
from helpers import log, run_lake_build, SPEC_DIR, SPEC_SRC_DIR, MODEL_ID
from stages.llm import generate_content_with_retry

try:
    # Aristotlelib is the SDK for the Aristotle formal reasoning API.
    import aristotlelib
    from aristotlelib import ProjectInputType, ProjectStatus
except ImportError:
    # Handle environment where SDK is not installed (e.g. initial setup).
    aristotlelib = None
    ProjectInputType = None
    ProjectStatus = None

def _generate_project_description(ctx: dict, main_content: str) -> str:
    """Ask Gemini to describe the project for Aristotle."""
    # We use Gemini to create a high-level summary of what the code does.
    # This helps the prover understand the intent and invariants.
    prompt = ctx.get("prompt", "")
    user_msg = f"""Write a project description that will be sent to Aristotle, an automated theorem prover for Lean 4.

Original specification:
{prompt}

Implementation:
```lean
{main_content}
```

Describe (2-3 paragraphs):
1. What the program does (high-level purpose)
2. Key functions/definitions and their expected behavior
3. Important properties that should hold (invariants, totality, correctness conditions)

Be specific about function names. Write *to* Aristotle, not *about* Aristotle."""

    try:
        # Robust generation with retries for rate limiting.
        resp = generate_content_with_retry(ctx["client"], MODEL_ID, user_msg)
        if resp.candidates and resp.candidates[0].content.parts:
            # Return the generated description text.
            return resp.candidates[0].content.parts[0].text
    except Exception as e:
        log(f"Failed to generate description: {e}")
    # Fallback description if the LLM call fails.
    return f"Verify the correctness of this Lean 4 implementation based on: {prompt}"

def run_stage_proving(ctx: dict) -> None:
    """Orchestrate the submission of Lean files to Aristotle."""
    log("=== Stage 2: Proving via Aristotle ===")

    # Graceful degradation if Aristotle tools are missing.
    if aristotlelib is None:
        log("WARNING: aristotlelib not installed, creating placeholder Verif.lean")
        _create_placeholder_verif()
        return

    # API credentials managed via Secret Manager / Environment.
    api_key = ctx["secrets"]["secrets"].get("ARISTOTLE_API_KEY", "") or os.environ.get("ARISTOTLE_API_KEY", "")
    if not api_key:
        log("WARNING: ARISTOTLE_API_KEY not set, creating placeholder Verif.lean")
        _create_placeholder_verif()
        return

    # Export credentials for the SDK to use.
    os.environ["ARISTOTLE_API_KEY"] = api_key

    # Collect all Lean files generated in Stage 1 for submission.
    # Find implementation files (Main.lean and any Module*.lean)
    impl_files = [f for f in SPEC_SRC_DIR.glob("*.lean") 
                  if f.name not in {"Prelude.lean", "Verif.lean"}]
    
    if not impl_files:
        log("No implementation files found")
        _create_placeholder_verif()
        return

    try:
        cwd = os.getcwd()
        # Move into the Lean project directory for submission.
        os.chdir(SPEC_DIR)
        # Async submission call.
        submission_result = asyncio.run(_submit_to_aristotle(ctx, impl_files))
        os.chdir(cwd)
    except Exception as e:
        log(f"Aristotle error: {e}")
        _create_placeholder_verif()

    # Generate a status report for the user.
    try:
        from stages.report import generate_report
        generate_report(ctx)
    except Exception:
        pass

    log("=== Stage 2 Complete ===")
    return submission_result if 'submission_result' in locals() else None

async def _submit_to_aristotle(ctx: dict, impl_files: list) -> None:
    # Verif.lean is the entry point for the formal proof.
    verif_path = SPEC_SRC_DIR / "Verif.lean"
    
    # 1. Read Verif.lean and add imports for any extra implementation files
    verif_content = verif_path.read_text()
    
    # Ensure all generated modules are imported so Aristotle can see them.
    # Add imports for any Module*.lean files not already imported
    extra_imports = []
    for f in impl_files:
        module_name = f.stem
        import_line = f"import Src.{module_name}"
        if import_line not in verif_content:
            extra_imports.append(import_line)
    
    if extra_imports:
        # Patch Verif.lean with necessary imports.
        # Insert extra imports after the existing import lines
        lines = verif_content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("import "):
                insert_idx = i + 1
        for imp in reversed(extra_imports):
            lines.insert(insert_idx, imp)
        verif_content = "\n".join(lines)
        verif_path.write_text(verif_content)
    
    # Build check ensures the Lean code is valid before external submission.
    if not run_lake_build(SPEC_DIR).startswith("Build Success"):
        return

    # 2. Construct the Prompt to Aristotle
    # We combine the project description, the existing Verif.lean template,
    # and the implementation code into a single context for the prover.
    # Generate a detailed description using Gemini, then ask Aristotle to prove theorems.
    all_content = "\n\n".join(f"-- {f.name}\n{f.read_text()}" for f in impl_files)
    description = _generate_project_description(ctx, all_content)
    
    desc_path = SPEC_DIR / "aristotle_request.txt"
    aristotle_prompt = f"""{description}

---

Write a complete Verif.lean file that verifies the correctness of this implementation.
Your output must be a valid Lean 4 file based on:

```lean
{verif_content}```

Replace the empty namespace body with actual theorems and proofs.
Focus on:
- Functional correctness of the main operations
- Totality (functions terminate on all valid inputs)  
- Key invariants and properties

The implementation code is:

```lean
{all_content}
```"""
    desc_path.write_text(aristotle_prompt)
    
    verif_rel = str(verif_path.relative_to(SPEC_DIR))
    # 3. Call Aristotle API
    # We provide:
    # - A high-level natural language request (informal input).
    # - The formal context (Verif.lean) to populate.
    # - Instructions to validate the resulting proofs.
    # We send two key inputs:
    #   - input_file_path: The request text (prompt + code)
    #   - formal_input_context: The context file (Verif.lean) to verify against
    result = await aristotlelib.Project.prove_from_file(
        input_file_path=str(desc_path.relative_to(SPEC_DIR)),
        project_input_type=ProjectInputType.INFORMAL,
        formal_input_context=verif_rel,
        auto_add_imports=True,
        validate_lean_project=True, # Validates that the generated proofs actually compile
        wait_for_completion=False,
    )
    if result:
        log(f"Aristotle job submitted: {result}")
    return result

def _create_placeholder_verif() -> None:
    # Initialize a minimal Verif.lean if tools are unavailable.
    path = SPEC_SRC_DIR / "Verif.lean"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""import Src.Prelude
import Src.Main

namespace Src
-- Placeholder: Aristotle not available
end Src
""")

async def download_aristotle_solution(aristotle_id: str, output_path: Path | str) -> tuple[str, str | None]:
    """Retrieve the formally verified solution from Arithmetic."""
    if aristotlelib is None:
        return "MISSING_LIB", None

    # Load project metadata by ID from the API.
    project = await aristotlelib.Project.from_id(aristotle_id)
    await project.refresh()
    status = project.status

    # Check for success status.
    if ProjectStatus is not None and status != ProjectStatus.COMPLETE:
        return str(status), None
    if ProjectStatus is None and str(status) != "COMPLETE":
        return str(status), None

    # Write the solution back to the local workspace.
    solution_path = await project.get_solution(output_path=str(output_path))
    return str(status), str(solution_path)

