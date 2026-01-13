#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import asyncio
import sys
import time
import tomllib
import json
from pathlib import Path
from pprint import pformat

from openai import OpenAI
try:
    import aristotlelib
except ImportError:
    aristotlelib = None

# ---------------- Configuration ----------------
# Standard configuration for the Anneal workspace
# These will be updated dynamically if run_agent is called with different paths
SECRETS_FILE = Path("secrets.toml")
SPEC_DIR = Path("spec")
GEMSPEC_PATH = SPEC_DIR / "Spec" / "GemSpec.lean"
PROGRAM_PATH = SPEC_DIR / "Spec" / "Program.lean"

# The "Rust Project" directory. In the test repo, it is "TestProject".
# In a real repo, it might be "." (the root).
TEST_PROJECT_DIR = Path("TestProject")

# ALLOWED_FILES will be populated at runtime
ALLOWED_FILES: set[str] = set()

MODEL_ID = "gpt-5.1-codex"
MAX_TURNS = 80
PRINT_TRUNC = 4000

# ---------------- Utilities ----------------
def log(msg: str) -> None:
    print(msg, flush=True)

def trunc(s: str, n: int = PRINT_TRUNC) -> str:
    if s is None:
        return ""
    return s if len(s) <= n else (s[:n] + f"\n... (truncated, total {len(s)} chars)")

def load_secrets() -> dict:
    if not SECRETS_FILE.exists():
        # Fallback: check if we have env var (for Cloud Run)
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            return {"secrets": {"OPENAI_API_KEY": key}}
        # Check for other keys just in case
        aristotle_key = os.environ.get("ARISTOTLE_API_KEY") 
        if aristotle_key:
             return {"secrets": {"OPENAI_API_KEY": key, "ARISTOTLE_API_KEY": aristotle_key}}
        raise FileNotFoundError(f"{SECRETS_FILE} not found and OPENAI_API_KEY not in env.")
    with SECRETS_FILE.open("rb") as f:
        return tomllib.load(f)

def build_allowlist(roots: list[Path]) -> set[str]:
    files: set[str] = set()
    ignore_dirs = {".lake", ".git", ".github", "target", "__pycache__", "lake-packages"}
    
    log("Building allowlist...")
    start_t = time.time()
    
    base_cwd = Path.cwd().resolve()

    for root in roots:
        # Resolve root to absolute to ensure os.walk yields absolute paths if we pass absolute, 
        # or we just be careful. Ideally we pass absolute root.
        root_abs = root.resolve()
        
        if not root_abs.exists():
            continue
        
        # optimized walk
        for dirpath, dirnames, filenames in os.walk(root_abs):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            
            for f in filenames:
                p_abs = Path(dirpath) / f
                try:
                    rel = p_abs.relative_to(base_cwd).as_posix()
                    files.add(rel)
                except ValueError:
                    pass
                    
    log(f"Allowlist built in {time.time() - start_t:.2f}s, {len(files)} files.")
    return files

# ---------------- Tools ----------------
def cat_file(relative_path: str) -> str:
    """Reads and returns the content of a file from allowlisted directories."""
    rp = Path(relative_path).as_posix()
    if rp not in ALLOWED_FILES:
        # Check if it was just a matter of ./ prefix
        if rp.startswith("./") and rp[2:] in ALLOWED_FILES:
             rp = rp[2:]
        else:
            return f"Error: Access denied. '{rp}' is not in the allowlist."
    
    target_path = Path(rp).resolve()
    try:
        return target_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file '{rp}': {e}"

def list_files(relative_path: str = ".") -> str:
    """Lists files in the project (directory listing)."""
    target = Path(relative_path).resolve()
    base = Path.cwd().resolve()
    
    # Security: Ensure we are within CWD and explicitly allowed roots or CWD itself
    # We want to allow listing '.' (CWD), 'TestProject', 'spec'
    
    try:
        rel = target.relative_to(base)
    except ValueError:
        return f"Error: Access denied. '{relative_path}' is outside project root."
    
    # Simple check: target must be CWD or inside one of the allowlisted roots?
    # Actually, if we just rely on cat_file being strict, list_files can be looser,
    # BUT we don't want to list .git or secrets.
    
    if not target.exists():
        return f"Error: Path not found: {relative_path}"
    if not target.is_dir():
        return f"Error: Not a directory: {relative_path}"
    
    entries = []
    for p in sorted(target.iterdir()):
        # Hide hidden files/dirs (like .git, .devcontainer)
        if p.name.startswith("."):
            continue
        # Hide sensitive files
        if p.name == "secrets.toml":
            continue
        entries.append(p.name + ("/" if p.is_dir() else ""))
        
    return "\n".join(entries)

import re

def verify_sorries(content: str) -> str | None:
    """
    Parses Lean content to ensure every theorem/lemma is proven with 'sorry'.
    Returns None if valid, or an error message string if invalid.
    """
    # Regex to find theorem declarations and their bodies
    # Matches: (protected/private) theorem/lemma <name> ... := <body> ending at next decl or EOF
    # We look for the ':=', then check if the immediate body starts with 'sorry' or 'by sorry'.
    
    decl_pattern = re.compile(
        r'^\s*(?:private\s+|protected\s+)?(?:theorem|lemma)\s+(?P<name>\S+)[\s\S]*?:=\s*(?P<body>[\s\S]*?)(?=\n\s*(?:theorem|lemma|def|structure|inductive|class|section|namespace|end|#|\Z))', 
        re.MULTILINE
    )
    
    # Simple check: scan line by line for 'theorem' / 'lemma' is harder due to multiline sigs.
    # The regex above relies on conventions (next decl starts at start of line).
    
    # A safer, simpler approach: 
    # Find start of every theorem/lemma, find the next ':=', checks what follows.
    
    matches = list(decl_pattern.finditer(content))
    if not matches:
        # If regex missed everything but 'theorem' is present, that's suspicious.
        if "theorem" in content or "lemma" in content:
            # Fallback simple check
            pass
        else:
             return None # No theorems, maybe just defs?

    for m in matches:
        name = m.group("name")
        body = m.group("body").strip()
        
        # Check if body starts with 'sorry' or 'by sorry'
        is_sorry = body.startswith("sorry") or body.startswith("by sorry") or body.startswith("by\n  sorry")
        
        if not is_sorry:
            return (
                f"Verification Failed: Theorem '{name}' is not sorry'd.\n"
                f"Body starts with: '{trunc(body, 50)}'\n"
                "You must prove ALL theorems using ':= sorry' or ':= by sorry'."
            )
            
    return None

def submit_final_spec(content: str) -> str:
    """
    Writes the content to spec/Spec/GemSpec.lean and runs `lake build`.
    This is the FINAL step to verify and submit the specification.
    """
    # Robust check for sorries
    error = verify_sorries(content)
    if error:
        return error

    try:
        GEMSPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
        GEMSPEC_PATH.write_text(content, encoding="utf-8")
    except Exception as e:
        return f"Error writing GemSpec.lean: {e}"
    
    start = time.time()
    try:
        result = subprocess.run(
            ["lake", "build"],
            cwd=str(SPEC_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as e:
        return f"Error executing build command: {e}"
    elapsed = time.time() - start
    
    if result.returncode == 0:
        return "Success"
    return (
        f"Build Failed (exit={result.returncode}, elapsed={elapsed:.2f}s)\n\n"
        f"--- STDERR ---\n{result.stderr}\n\n"
        f"--- STDOUT ---\n{result.stdout}"
    )

TOOLS_SCHEMA = [
    {
        "type": "function",
        "name": "cat_file",
        "description": "Reads a file from the project (must be in allowlist).",
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {"type": "string", "description": "Path relative to project root (CWD)"}
            },
            "required": ["relative_path"]
        }
    },
    {
        "type": "function",
        "name": "list_files",
        "description": "Lists contents of a directory in the project.",
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {"type": "string", "description": "Path relative to project root (CWD), default '.'"}
            }
        }
    },
    {
        "type": "function",
        "name": "submit_final_spec",
        "description": "Submits the final GemSpec.lean content for validation and build. Call this when you are ready to prove correctness.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The full content of the GemSpec.lean file"}
            },
            "required": ["content"]
        }
    }
]

def map_function_calls(tool_calls):
    calls = []
    if tool_calls:
        for tc in tool_calls:
            calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "args": json.loads(tc.function.arguments)
            })
    return calls

def run_agent(project_root: Path = Path("."), rust_subdir: str = "TestProject"):
    """
    Run the agent loop.
    :param project_root: The root of the workspace (where main.py is assumed to run).
    :param rust_subdir: Subdirectory containing the Rust project (e.g. 'src' or '.').
    """
    global ALLOWED_FILES, TEST_PROJECT_DIR, SPEC_DIR, GEMSPEC_PATH, PROGRAM_PATH
    
    # Update paths based on arguments
    TEST_PROJECT_DIR = project_root / rust_subdir
    SPEC_DIR = project_root / "spec"
    GEMSPEC_PATH = SPEC_DIR / "Spec" / "Verif.lean"
    PROGRAM_PATH = SPEC_DIR / "Spec" / "Program.lean"
    
    log(f"=== Boot (OpenAI Responses API) ===")
    log(f"MODEL_ID: {MODEL_ID}")
    log(f"Workspace Root: {project_root.resolve()}")
    log(f"Rust Project: {TEST_PROJECT_DIR}")
    log(f"Spec Dir: {SPEC_DIR}")
    
    ALLOWED_FILES = build_allowlist([TEST_PROJECT_DIR, SPEC_DIR])
    
    secrets = load_secrets()
    api_key = secrets.get("secrets", {}).get("OPENAI_API_KEY")
    if not api_key or api_key == "INSERT_YOUR_KEY_HERE":
        log("Error: OPENAI_API_KEY missing in secrets.toml/env.")
        return # Exit gracefully
        
    client = OpenAI(api_key=api_key)
    
    if PROGRAM_PATH.exists():
        program_content = PROGRAM_PATH.read_text(encoding="utf-8")
    else:
        program_content = "Error: Program.lean not found."
    
    # Initialize Context
    initial_prompt = f"""You are an expert formal verification engineer specializing in Lean 4.
Your goal is to generate a valid Lean 4 specification file (`Verif.lean`) that formally checks the content in `Program.lean`.

Context:
`Program.lean` content is located at `{PROGRAM_PATH.relative_to(project_root)}`.
`Verif.lean` will be located at `{GEMSPEC_PATH.relative_to(project_root)}`.

`Program.lean` content:
```lean
{program_content}
```

Instructions:
1. Start by calling `list_files` (e.g., `list_files(".")`) to see the project root.
2. Explore code using `cat_file`.
3. Generate `Verif.lean` specifying the properties. 
    - **CRITICAL PRINCIPLE**: Think critically about what the code *actually* does, not just the "happy path".
    - Your specifications must be mathematically rigorous. they should capture the true behavior.
    - If `Program.lean` contains functions with error modes (e.g. `Result`), account for them.
    - Do NOT prove the theorems. Use `sorry` for all proofs.
4. Call `submit_final_spec` to submit your work and verify.
    - If it returns "Success", you are done. The loop will stop.
    - If it returns build errors or submission failure (e.g. missing `sorry`), analyze them and retry by calling `submit_final_spec` again with fixed content.
"""
    
    log("--- Starting Responses Loop ---")
    current_input = initial_prompt
    previous_response_id = None
    
    for turn in range(MAX_TURNS):
        log(f"\n=== Turn {turn + 1} ===")
        
        try:
            # Responses API call
            kwargs = {
                "model": MODEL_ID,
                "input": current_input,
                "tools": TOOLS_SCHEMA,
            }
            if previous_response_id:
                kwargs["previous_response_id"] = previous_response_id
                
            response = client.responses.create(**kwargs)
        except Exception as e:
            log(f"OpenAI API Error: {e}")
            break
            
        previous_response_id = response.id
        
        # Parse output
        has_tool_calls = False
        tool_outputs = []
        
        if getattr(response, 'output', None):
            for item in response.output:
                if item.type == "message":
                    # Item is ResponseOutputMessage
                    for content_part in item.content:
                        if content_part.type == "output_text":
                            log(f"Model: {content_part.text}")
                
                elif item.type == "function_call":
                    # Item is ResponseFunctionToolCall
                    has_tool_calls = True
                    func_name = item.name
                    call_id = item.call_id
                    args_str = item.arguments
                    
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}
                    
                    log(f"Tool Call: {func_name}({trunc(str(args), 100)})")
                    
                    result_str = "Error: Unknown tool"
                    if func_name == "cat_file":
                        result_str = cat_file(**args)
                    elif func_name == "list_files":
                        result_str = list_files(**args)
                    elif func_name == "submit_final_spec":
                        result_str = submit_final_spec(**args)
                    
                    log(f"Tool Output: {trunc(result_str, 500)}")
                    
                    if func_name == "submit_final_spec" and result_str.strip() == "Success":
                         log("!!! SUCCESS VERIFIED !!!")
                         
                         # --- Aristotle Integration ---
                         aristotle_key = secrets.get("secrets", {}).get("ARISTOTLE_API_KEY")
                         if not aristotle_key or "INSERT" in aristotle_key:
                             log("Warning: ARISTOTLE_API_KEY not configured. Skipping automated proving.")
                             return

                         if not aristotlelib:
                             log("Warning: aristotlelib not installed. Skipping automated proving.")
                             return

                         log("=== Calling Aristotle (Vibe Proving) ===")
                         os.environ["ARISTOTLE_API_KEY"] = aristotle_key
                         
                         try:
                             # Using prove_from_file with auto_add_imports=True (built-in way to handle context)
                             # validate_lean_project=True ensures checking the project structure
                             log(f"Submitting {GEMSPEC_PATH} to Aristotle...")
                             
                             # Note: prove_from_file returns the path to the solution OR project_id if async.
                             # Default is wait_for_completion=True.
                             # Change CWD to spec dir so aristotlelib/lake can resolve relative paths
                             original_cwd = os.getcwd()
                             os.chdir(SPEC_DIR)
                             log(f"Changed CWD to {SPEC_DIR} for Aristotle call")
                             
                             try:
                                 # It is an async function, so we must run it in an event loop.
                                 # Note: input_file_path should be relative to the new CWD or absolute. 
                                 # GEMSPEC_PATH is relative to root (spec/Spec/GemSpec.lean).
                                 # We are in spec/, so we want Spec/GemSpec.lean.
                                 target_file = GEMSPEC_PATH.relative_to(SPEC_DIR)
                                 
                                 result = asyncio.run(aristotlelib.Project.prove_from_file(
                                     input_file_path=str(target_file),
                                     auto_add_imports=True,
                                     validate_lean_project=True,
                                     wait_for_completion=True
                                 ))
                             finally:
                                 os.chdir(original_cwd)
                                 log(f"Restored CWD to {original_cwd}")
                             
                             log(f"Aristotle Proof Complete. Result saved to: {result}")
                             
                             # If result is a path, let's copy/rename it to GemSpec.lean to become the canonical source
                             # Result is relative to SPEC_DIR because we ran it there
                             result_path = SPEC_DIR / result
                             if result_path.exists():
                                 # Backup original just in case (optional, but polite)
                                 # GEMSPEC_PATH.rename(GEMSPEC_PATH.with_suffix(".lean.bak"))
                                 
                                 # Overwrite
                                 result_path.rename(GEMSPEC_PATH)
                                 log(f"Final proved spec saved to: {GEMSPEC_PATH} (overwriting original)")

                                 # Run final verification build
                                 log("Running final `lake build` to verify proved spec...")
                                 build_res = subprocess.run(
                                     ["lake", "build"],
                                     cwd=str(SPEC_DIR),
                                     capture_output=True,
                                     text=True,
                                     check=False
                                 )
                                 if build_res.returncode == 0:
                                     log("!!! FINAL BUILD SUCCESSFUL !!!")
                                 else:
                                     log(f"Warning: Final build failed (exit={build_res.returncode}). Check GemSpec.lean manually.")
                                     log(f"STDERR: {build_res.stderr}")
                             
                         except Exception as ari_err:
                             log(f"Aristotle Error: {ari_err}")
                             # We don't fail the whole agent run, as spec generation was successful.
                         
                         return

                    # Construct proper tool output item for next input
                    tool_outputs.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result_str
                    })

        if not has_tool_calls:
            log("No tool calls. Checking for done signal...")
            # If no tools called, checking if we are done or just chatting.
            # In this autonomous loop, we generally stop if no tools are used
            # unless we interpret the text as completion.
            # But usually we loop until test_gemspec returns success.
            log("Stalled? Stopping.")
            break
            
        # Update current_input for the next turn
        current_input = tool_outputs

def main():
    run_agent()

if __name__ == "__main__":
    main()
