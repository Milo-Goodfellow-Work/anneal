import subprocess, sys, os

def rust_lean(src):
    # Get name of crate root dir
    crate_name = os.path.basename(os.path.normpath(src))
    # LLBC filename (relative to cwd=src below)
    llbc_path = crate_name + '.llbc'

    # Spec Lake project (sibling of crate dir)
    spec_root = os.path.join(os.path.dirname(os.path.abspath(src)), 'spec')
    # Generate directly into the Spec library folder
    lean_dir = os.path.join(spec_root, 'Spec')

    # Generate llbc file
    subprocess.run(['charon', 'cargo', '--preset=aeneas'], cwd=src, check=True)

    # Generate Lean into spec/Spec/
    subprocess.run(['aeneas', '-backend', 'lean', '-dest', lean_dir, llbc_path], cwd=src, check=True)

    # Convert from snake case to camel to get generated Lean file name / module name
    lean_name = ''.join(part.capitalize() for part in crate_name.split('_'))

    # Append import into the Spec root module (NO checks)
    with open(os.path.join(spec_root, 'Spec.lean'), 'a') as f:
        f.write(f"import Spec.{lean_name}\n")

    # Return generated Lean
    return open(os.path.join(lean_dir, f"{lean_name}.lean"), 'r').read()

print(rust_lean("./TestProject"))
