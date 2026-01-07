#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
import tomllib
import json
from pathlib import Path
from pprint import pformat

from openai import OpenAI

# ---------------- Configuration ----------------
SECRETS_FILE = Path("secrets.toml")
SPEC_DIR = Path("spec")
GEMSPEC_PATH = SPEC_DIR / "Spec" / "GemSpec.lean"
EXTRACT_PATH = SPEC_DIR / "Spec" / "Extract.lean"
TEST_PROJECT_DIR = Path("TestProject")

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
        raise FileNotFoundError(f"{SECRETS_FILE} not found.")
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

ALLOWED_FILES: set[str] = set()

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

def main():
    global ALLOWED_FILES
    log("=== Boot (OpenAI Responses API) ===")
    log(f"MODEL_ID: {MODEL_ID}")
    
    ALLOWED_FILES = build_allowlist([TEST_PROJECT_DIR, SPEC_DIR])
    
    secrets = load_secrets()
    api_key = secrets.get("secrets", {}).get("OPENAI_API_KEY")
    if not api_key or api_key == "INSERT_YOUR_KEY_HERE":
        log("Error: OPENAI_API_KEY missing in secrets.toml.")
        sys.exit(1)
        
    client = OpenAI(api_key=api_key)
    
    if EXTRACT_PATH.exists():
        extract_content = EXTRACT_PATH.read_text(encoding="utf-8")
    else:
        extract_content = "Error: Extract.lean not found."
    
    # Path B: Use a prompt string for the first input
    initial_prompt = f"""You are an expert formal verification engineer specializing in Lean 4 and Rust.
Your goal is to generate a valid Lean 4 specification file (`GemSpec.lean`) that formally checks the extracted code in `Extract.lean`.

Context:
`Extract.lean` content is located at `spec/Spec/Extract.lean`.
`GemSpec.lean` will be located at `spec/Spec/GemSpec.lean`.

`Extract.lean` content:
```lean
{extract_content}
```

Instructions:
1. Start by calling `list_files` (e.g., `list_files(".")`) to see the project root.
2. Explore code using `cat_file` (e.g., `cat_file("spec/Spec/Extract.lean")` or `cat_file("TestProject/src/main.rs")`).
3. Generate `GemSpec.lean` specifying the properties. IMPORTANT: Do NOT prove the theorems. Use `sorry` for all proofs.
4. Call `submit_final_spec` to submit your work and verify.
    - If it returns "Success", you are done. The loop will stop.
    - If it returns build errors or submission failure (e.g. missing `sorry`), analyze them and retry by calling `submit_final_spec` again with fixed content.
"""
    
    log("--- Starting Responses Loop ---")
    
    # We maintain the "current input" to send to the model.
    # Initially, it's just the user prompt.
    # Subsequently, it will be the list of tool outputs from the *previous* turn.
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

if __name__ == "__main__":
    main()
