"""Scaffold generation for prompt-driven projects."""
from __future__ import annotations
from pathlib import Path
from helpers import log, SPEC_DIR, SPEC_SRC_DIR, SPEC_TESTS_DIR, SPEC_REPORTS_DIR, ensure_prelude_and_lockdown

def create_project_from_prompt(ctx: dict) -> None:
    """Create project structure for prompt-driven generation."""
    ensure_prelude_and_lockdown()
    
    name = ctx["name"]
    SPEC_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ctx["spec_project_root"].mkdir(parents=True, exist_ok=True)
    ctx["source_root"].mkdir(parents=True, exist_ok=True)
    
    ctx["impl_extensions"] = [".c", ".h"]
    main_lean = f"{name}/Main.lean"
    verif_lean = f"{name}/Verif.lean"
    harness_lean = "tests/Harness.lean"
    
    ctx["allowed_lean_writes"] = {main_lean, verif_lean, harness_lean}
    ctx["allowed_impl_writes"] = set()
    for i in range(1, 6):
        ctx["allowed_lean_writes"].add(f"{name}/Module{i}.lean")
    
    gen_rel = "spec/tests/gen_inputs.py"
    c_harness_rel = "spec/tests/harness.c"
    ctx["allowed_text_writes"] = {gen_rel, c_harness_rel}
    
    # Create stub files if they don't exist
    _create_stub(ctx["spec_src_root"] / main_lean, f"import Spec.Prelude\n\nnamespace Spec.{name}\n\nend Spec.{name}\n")
    _create_stub(ctx["spec_src_root"] / verif_lean, f"import Spec.Prelude\nimport Spec.{name}.Main\n\nnamespace Spec.{name}\n\nend Spec.{name}\n")
    
    harness_path = ctx["spec_src_root"] / harness_lean
    harness_path.parent.mkdir(parents=True, exist_ok=True)
    _create_stub(harness_path, _harness_template(name))
    
    _create_stub(Path(gen_rel), _gen_inputs_template())
    _create_stub(Path(c_harness_rel), _c_harness_template())
    
    # Project root module
    _create_stub(ctx["spec_src_root"] / f"{name}.lean", f"import Spec.{name}.Main\nimport Spec.{name}.Verif\n")
    
    # Register in Spec.lean
    spec_file = SPEC_SRC_DIR.parent / "Spec.lean"
    line = f"import Spec.{name}"
    if spec_file.exists():
        content = spec_file.read_text()
        if line not in content:
            spec_file.write_text(content.rstrip() + "\n" + line + "\n")
    else:
        spec_file.write_text(line + "\n")
    
    ctx["locked_lean_paths"].add("Prelude.lean")
    ctx["locked_lean_paths"].add(f"{name}.lean")
    ctx["src_to_lean"] = {"(prompt)": main_lean}
    ctx["lean_to_src"] = {main_lean: "(prompt)"}

def _create_stub(path: Path, content: str):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

def _harness_template(name: str) -> str:
    return f"""import Spec.Prelude
import Spec.{name}

namespace Spec.{name}

partial def readLines (acc : List String) : IO (List String) := do
  let stdin ← IO.getStdin
  let line ← stdin.getLine
  if line.isEmpty then return acc.reverse
  else readLines (line.trim :: acc)

def main : IO Unit := do
  let lines ← readLines []
  for line in lines do
    if line == "NOOP" then IO.println "OK"
    else IO.println "ERR"

end Spec.{name}
"""

def _gen_inputs_template() -> str:
    return """#!/usr/bin/env python3
import argparse, random

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--n', type=int, required=True)
    args = ap.parse_args()
    random.seed(args.seed)
    for _ in range(args.n):
        print('NOOP')

if __name__ == '__main__':
    main()
"""

def _c_harness_template() -> str:
    return """#include <stdio.h>
#include <string.h>

int main(void) {
    char buf[512];
    while (fgets(buf, sizeof(buf), stdin)) {
        size_t n = strlen(buf);
        while (n && (buf[n-1] == '\\n' || buf[n-1] == '\\r')) { buf[n-1] = 0; n--; }
        if (n == 0) continue;
        if (strcmp(buf, "NOOP") == 0) puts("OK");
        else puts("ERR");
    }
    return 0;
}
"""
