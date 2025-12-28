'''

'''

import subprocess, sys, os

def rust_lean(src):
    # Get name of crate root dir
    crate_name = os.path.basename(os.path.normpath(src))
    # And relative path of Charon gen'd llbc
    llbc_path = os.path.join(src, crate_name + '.llbc')

    # Create Lake Lean project
    lean_dir = os.path.join(os.path.dirname(os.path.abspath(src)), 'spec')

    # Generate llbc file
    subprocess.run(['charon', 'cargo', '--preset=aeneas'], cwd=src, check=True)

    # Generate Lean
    subprocess.run(['aeneas', '-backend', 'lean', '-dest', lean_dir, llbc_path], cwd=src, check=True)

    # Convert from snake case to camel to get generated Lean file name
    lean_name = ''.join(part.capitalize() for part in crate_name.split('_'))

    # Get generated Lean
    return open(f'{lean_dir}/{lean_name}.lean', 'r').read()

# src = os.path.expanduser(sys.argv[1])
# gend_file = open('Generated.lean', 'w+')
print(rust_lean("./TestProject"))