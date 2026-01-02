import subprocess, sys, os

def rust_lean(src):
    src_abs = os.path.abspath(src)
    crate_name = os.path.basename(os.path.normpath(src_abs))
    
    spec_root = os.path.join(os.path.dirname(src_abs), 'spec')
    lean_dir = os.path.join(spec_root, 'Spec')
    llbc_path = crate_name + '.llbc'

    # 1. Generate .llbc
    subprocess.run(['charon', 'cargo', '--preset=aeneas'], cwd=src_abs, check=True)

    # 2. Generate Lean and CAPTURE output
    #    We assume the log is printed to stdout or stderr.
    result = subprocess.run(
        ['aeneas', '-backend', 'lean', '-dest', lean_dir, llbc_path], 
        cwd=src_abs, 
        check=True, 
        capture_output=True, 
        text=True
    )

    # 3. Find the generated filename from logs
    #    Looking for: "[Info ] Generated: /path/to/File.lean"
    generated_path = None
    
    # Check both stdout and stderr just to be safe
    combined_logs = result.stdout + "\n" + result.stderr
    
    for line in combined_logs.splitlines():
        if "Generated:" in line and line.strip().endswith(".lean"):
            # Split by "Generated:" and take the last part (the path)
            generated_path = line.split("Generated:")[-1].strip()
            break
            
    # 4. Process the file
    #    Derive the module name from the actual filename Aeneas used
    filename = os.path.basename(generated_path)
    module_name = os.path.splitext(filename)[0]
    
    with open(generated_path, 'r') as f:
        content = f.read()

    # Replace the namespace and write to Extract.lean
    new_content = content.replace(module_name, "Extract")

    target_path = os.path.join(lean_dir, "Extract.lean")
    with open(target_path, 'w') as f:
        f.write(new_content)

    # Delete the original
    os.remove(generated_path)

    return new_content

if __name__ == "__main__":
    rust_lean("TestProject")