'''
'''

import subprocess, sys, os

def rust_lean(src):
    # Get name of crate root dir
    crate_name = os.path.basename(os.path.normpath(src))
    # Path of Charon gen'd llbc (relative to cwd=src)
    llbc_path = crate_name + '.llbc'

    # Use existing spec Lake project next to src, and generate directly into its Lean lib dir
    lean_proj = os.path.join(os.path.dirname(os.path.abspath(src)), 'spec')
    lean_dir = os.path.join(lean_proj, 'Spec')

    # Generate llbc file
    subprocess.run(['charon', 'cargo', '--preset=aeneas'], cwd=src, check=True)

    # Generate Lean directly into spec/Spec
    subprocess.run(['aeneas', '-backend', 'lean', '-dest', lean_dir, llbc_path], cwd=src, check=True)

    # Convert from snake case to camel to get generated Lean file name
    if '_' in crate_name:
        lean_name = ''.join(part.capitalize() for part in crate_name.split('_'))
    else:
        lean_name = crate_name

    # Add generated module to the Spec project
    with open(os.path.join(lean_proj, 'Spec.lean'), 'a') as f:
        f.write(f'\nimport Spec.{lean_name}\n')

    # Get generated Lean
    return open(f'{lean_dir}/{lean_name}.lean', 'r').read()

print(rust_lean("./TestProject"))
