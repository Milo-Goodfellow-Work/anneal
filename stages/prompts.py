"""Prompt builders for LLM."""
from __future__ import annotations
from helpers import SPEC_SRC_DIR

def base_instructions_prompt_cogen(prompt: str) -> str:
    return f"""ROLE: Co-Generation Engine - generate C implementation AND Lean 4 equivalent.
SETTING: SAFETY-CRITICAL. Correctness mandatory. No placeholders/stubs.

IMPLEMENTATION DIR: generated/
LEAN DIR: spec/Src/

WRITABLE FILES:
- generated/*.c, generated/*.h (C implementation)
- spec/Src/Main.lean, spec/Src/Module*.lean (Lean implementation)
- spec/Src/tests/Harness.lean (test harness)
- spec/tests/gen_inputs.py, spec/tests/harness.c (test generators)

LOCKED: spec/Src/Prelude.lean (do not modify)

IMPORTS:
- Prelude.lean provides: Std, HashMap, HashSet, TreeMap, TreeSet, U8/U16/U32/U64
- If you need Mathlib functionality, add specific imports to Main.lean:
  - `import Mathlib.Data.Nat.Basic` for Nat lemmas
  - `import Mathlib.Data.List.Lemmas` for List lemmas  
  - `import Mathlib.Tactic` for tactics (omega, linarith, simp, etc.)
  - `import Mathlib.Data.Fin.Basic` for Fin type
- Do NOT use `import Mathlib` (imports everything, too slow)

SPECIFICATION:
{prompt}

DELIVERABLES:
1. C implementation in generated/
2. Lean 4 definitions in spec/Src/Main.lean
3. Test generator: spec/tests/gen_inputs.py
4. C harness: spec/tests/harness.c
5. Lean harness: spec/Src/tests/Harness.lean
6. Test description: When you call submit_stage, include in your summary a "comment" explaining:
   - What everyday data types the program takes as input (e.g., "two integers")
   - What it returns as output (e.g., "one integer: their sum")
   - How to read each test case in the report

LEAN 4 IO:
  let stdin ← IO.getStdin
  let line ← stdin.getLine  -- returns String with newline
  if line.isEmpty then ...  -- EOF

PROCESS:
1. Write Main.lean
2. Read Main.lean back to confirm names
3. Write Harness.lean with exact names
4. Run differential tests
5. CRITICAL: Review the differential test output manually. Verify that the output is CORRECT according to the specification, not just that C and Lean match.
   - If both produce the same WRONG answer, you must fix both.
   - Check edge cases manually.
6. Fix mismatches or incorrect logic until tests pass AND are correct
7. Call submit_stage

RULES:
- NO 'sorry' anywhere
- Each module MUST 'import Src.Prelude'
- Use 'namespace Src' / 'end Src'
- Tests: 5 runs x 5 cases minimum
"""
