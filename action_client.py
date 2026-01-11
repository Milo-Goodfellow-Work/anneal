import os
import sys
import json
import base64
import requests

def main():
    service_url = os.environ.get("INPUT_SERVICE_URL")
    repo_url = os.environ.get("INPUT_REPO_URL")
    # Optional: Authentication (if Service is secured or if passing keys)
    # api_key = os.environ.get("INPUT_API_KEY") 

    if not service_url:
        print("Error: 'service_url' input is required.")
        sys.exit(1)
    if not repo_url:
        print("Error: 'repo_url' input is required.")
        sys.exit(1)

    print(f"Anneal Action Client")
    print(f"Target Service: {service_url}")
    print(f"Repository: {repo_url}")

    # Construct Payload
    # We follow the Pub/Sub Push format required by worker.py
    job = {"repo_url": repo_url}
    job_json = json.dumps(job)
    data_b64 = base64.b64encode(job_json.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": {
            "data": data_b64,
            "messageId": "action-client-id"
        }
    }

    try:
        print("Sending verification request...")
        resp = requests.post(
            service_url, 
            json=payload, 
            headers={"Content-Type": "application/json"}
        )
        print(f"Response Status: {resp.status_code}")
        print(f"Response Body: {resp.text}")
        
        if resp.status_code != 200:
            print("Verification failed (server returned non-200).")
            sys.exit(1)
            
        print("Verification request submitted successfully.")
        
    except Exception as e:
        print(f"Request failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
