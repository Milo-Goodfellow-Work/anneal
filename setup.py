import subprocess, os

def to_camel_case(s: str) -> str:
    result = []
    capitalize_next = True

    for c in s:
        if c == "_":
            capitalize_next = True
        else:
            result.append(c.upper() if capitalize_next else c)
            capitalize_next = False

    return "".join(result)

def rust_lean(src):
    src_abs = os.path.abspath(src)
    crate_name = os.path.basename(os.path.normpath(src_abs))
    
    spec_root = os.path.join(os.path.dirname(src_abs), 'spec')
    lean_dir = os.path.join(spec_root, 'Spec')
    llbc_path = crate_name + '.llbc'

    # Generate .llbc
    subprocess.run(
        ['charon', 'cargo', '--preset=aeneas'], 
        cwd=src_abs, 
        check=True
    )

    # Generate Lean using the 'Extract' namespace we standardize
    subprocess.run(
        ['aeneas', '-backend', 'lean', '-dest', '-namespace',
            lean_dir, llbc_path, 'Extract'],
        cwd=src_abs,
        check=True,
    )

    # Convert the crate name to camel case, combine to get path
    #    Aeneas uses camel for the Lean file it generates: https://github.com/AeneasVerif/aeneas/blob/47b9e7456ea6b1cd8ee5e1aba15f70ff20f75c04/src/Translate.ml#L1842
    generated_path = os.path.join(lean_dir, to_camel_case(crate_name))

    # Write og file content to Extract.lean, then delete the og file
    new_content = None
    with open(generated_path, 'r') as f:
        new_content = f.read()

    target_path = os.path.join(lean_dir, "Extract.lean")
    with open(target_path, 'w') as f:
        f.write(new_content)

    # Delete the original
    os.remove(generated_path)

if __name__ == "__main__":
    rust_lean("TestProject")