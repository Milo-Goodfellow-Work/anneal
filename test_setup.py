import os
import setup

def test_rust_lean_execution():
    print("TEST: Running rust_lean on ./TestProject...")
    
    # 1. Run the function
    try:
        content = setup.rust_lean("./TestProject")
    except Exception as e:
        print(f"FAIL: Function crashed with error: {e}")
        return

    # Resolve paths for verification
    base_dir = os.path.dirname(os.path.abspath("./TestProject"))
    spec_root = os.path.join(base_dir, 'spec')
    lean_dir = os.path.join(spec_root, 'Spec')
    spec_file = os.path.join(spec_root, 'Spec.lean')
    
    # 2. Verify Output Content
    if not content or len(content) == 0:
        print("FAIL: rust_lean returned empty content.")
        return
    print("PASS: Content returned successfully.")

    # 3. Verify Spec.lean imports
    with open(spec_file, 'r') as f:
        spec_content = f.read()
    
    if "import Spec.TestProject" not in spec_content:
        print("FAIL: Spec.lean does not contain 'import Spec.TestProject'")
    elif "import Spec.Basic" in spec_content:
        print("FAIL: Spec.lean still contains 'import Spec.Basic'")
    else:
        print("PASS: Spec.lean imports look correct.")

    # 4. Verify Cleanup (Main.lean and Basic.lean should be GONE)
    if os.path.exists(os.path.join(spec_root, "Main.lean")):
        print("FAIL: Main.lean was NOT removed.")
    else:
        print("PASS: Main.lean removed.")

    if os.path.exists(os.path.join(lean_dir, "Basic.lean")):
        print("FAIL: Basic.lean was NOT removed.")
    else:
        print("PASS: Basic.lean removed.")

if __name__ == "__main__":
    test_rust_lean_execution()