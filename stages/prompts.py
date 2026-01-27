"""Prompt builders for LLM."""
from __future__ import annotations
from pathlib import Path
from helpers import SPEC_DIR, SPEC_SRC_DIR, list_lean_files, list_project_files

def _files_list(ctx: dict, key: str) -> str:
    return "\n".join(sorted(ctx.get(key, set())))

def base_instructions_prompt_cogen(ctx: dict) -> str:
    prompt = ctx.get("prompt", "")
    
    return f"""ROLE: Co-Generation Engine - generate C implementation AND Lean 4 equivalent.
SETTING: SAFETY-CRITICAL. Correctness mandatory. No placeholders/stubs.

IMPLEMENTATION DIR: {ctx['source_root']}
LEAN DIR: {ctx['spec_src_root']}/

WRITABLE LEAN FILES:
{_files_list(ctx, 'allowed_lean_writes')}

WRITABLE TEXT FILES:
{_files_list(ctx, 'allowed_text_writes')}

SPECIFICATION:
{prompt}

DELIVERABLES:
1. C implementation in {ctx['source_root']}/
2. Lean 4 definitions in spec/Src/Main.lean
3. Test generator: spec/tests/gen_inputs.py
4. C harness: spec/tests/harness.c
5. Lean harness: spec/Src/tests/Harness.lean

LEAN 4 IO:
  let stdin ← IO.getStdin
  let line ← stdin.getLine  -- returns String with newline
  if line.isEmpty then ...  -- EOF

PROCESS:
1. Write Main.lean
2. Read Main.lean back to confirm names
3. Write Harness.lean with exact names
4. Run differential tests
5. Fix mismatches until tests pass
6. Call submit_stage

RULES:
- NO 'sorry' anywhere
- Each module MUST 'import Src.Prelude'
- Use 'namespace Src' / 'end Src'
- Tests: 5 runs x 5 cases minimum
"""
