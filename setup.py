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

    # Remove Basic.lean if it exists
    basic_lean = os.path.join(lean_dir, "Basic.lean")
    if os.path.exists(basic_lean):
        os.remove(basic_lean)

    # Remove Main.lean if it exists (Library-only build)
    main_lean = os.path.join(spec_root, "Main.lean")
    if os.path.exists(main_lean):
        os.remove(main_lean)

    # Wipe Spec.lean clean so it starts empty
    with open(os.path.join(spec_root, 'Spec.lean'), 'w') as f:
        f.write("-- This module serves as the root of the `Spec` library.\n")
        f.write("-- Import modules here that should be built as part of the library.\n\n")

    # Generate llbc file
    subprocess.run(['charon', 'cargo', '--preset=aeneas'], cwd=src, check=True)

    # Generate Lean into spec/Spec/
    subprocess.run(['aeneas', '-backend', 'lean', '-dest', lean_dir, llbc_path], cwd=src, check=True)

    # Convert from snake case to camel to get generated Lean file name / module name
    lean_name = ''.join(part.capitalize() for part in crate_name.split('_'))

    # Append import into the Spec root module
    with open(os.path.join(spec_root, 'Spec.lean'), 'a') as f:
        f.write(f"import Spec.{lean_name}\n")

    # Return generated Lean
    return open(os.path.join(lean_dir, f"{lean_name}.lean"), 'r').read()