import os
import json
import base64
import shutil
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request

import main
import setup

app = Flask(__name__)

# Locate the 'spec' template in the container (assumed CWD of worker.py)
SPEC_TEMPLATE_DIR = Path("spec").resolve()

@app.route("/", methods=["POST"])
def index():
    """
    Receive Pub/Sub push messages.
    """
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    pubsub_message = envelope["message"]

    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        try:
            data = base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
            # Handle potential double-encoding if pusher sends json string as data
            try:
                job = json.loads(data)
            except json.JSONDecodeError:
                # Maybe it is just a string?
                job = {"repo_url": data} 
        except Exception as e:
            msg = f"Invalid Pub/Sub message data: {e}"
            print(f"error: {msg}")
            return f"Bad Request: {msg}", 400
    else:
        # Empty message?
        return "OK", 200

    repo_url = job.get("repo_url")
    if not repo_url:
        print("Error: No repo_url in job")
        return "Bad Request: No repo_url", 400

    print(f"Processing job for: {repo_url}")
    
    # Create a temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_root = Path(temp_dir)
        print(f"Workspace: {workspace_root}")
        
        # 1. Clone the repository
        # We clone into a subdirectory 'repo' or use the root?
        # Let's clone into 'repo_name' inferring from url, or just 'project'
        project_name = repo_url.split("/")[-1].replace(".git", "")
        project_path = workspace_root / project_name
        
        try:
            print(f"Cloning {repo_url}...")
            subprocess.run(["git", "clone", repo_url, str(project_path)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Clone failed: {e}")
            return f"Clone failed: {e}", 500

        # 2. Inject 'spec' directory
        # Setup.py expects 'spec' to be a sibling of the rust project root if using rust_lean?
        # Actually setup.py: spec_root = os.path.join(os.path.dirname(src_abs), 'spec')
        # If project_path is /tmp/workspace/project
        # Then dirname is /tmp/workspace
        # So we should put 'spec' at /tmp/workspace/spec
        
        try:
            target_spec_dir = workspace_root / "spec"
            print(f"Copying spec template to {target_spec_dir}...")
            shutil.copytree(SPEC_TEMPLATE_DIR, target_spec_dir)
        except Exception as e:
             print(f"Failed to copy spec: {e}")
             return f"Setup failed: {e}", 500
             
        # 3. Run Extraction (Charon + Aeneas)
        # setup.rust_lean takes the path to the rust project
        try:
            print("Running extraction...")
            # We need to temporarily switch CWD or allow setup to handle it?
            # setup.rust_lean uses full paths, so it should be fine.
            # But it also generates .llbc in the rust dir.
            setup.rust_lean(str(project_path))
        except Exception as e:
            print(f"Extraction failed: {e}")
            return f"Extraction failed: {e}", 500
            
        # 4. Run Agent
        try:
            print("Starting Agent Loop...")
            # main.run_agent takes (project_root, rust_subdir)
            # project_root should be the workspace root (parent of project and spec)
            # rust_subdir should be project_name
            main.run_agent(project_root=workspace_root, rust_subdir=project_name)
        except Exception as e:
             print(f"Agent failed: {e}")
             return f"Agent failed: {e}", 500

    print("Job completed successfully.")
    return "OK", 200

if __name__ == "__main__":
    # Determine port for Cloud Run (default 8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
