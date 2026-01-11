import argparse
import base64
import json
import requests
import sys

def main():
    parser = argparse.ArgumentParser(description="Simulate a Pub/Sub Push to the worker.")
    parser.add_argument("--repo", required=True, help="Git repository URL to process")
    parser.add_argument("--url", default="http://localhost:8080", help="Worker URL")
    
    args = parser.parse_args()
    
    # Construct the job payload
    job = {
        "repo_url": args.repo
    }
    job_json = json.dumps(job)
    
    # Pub/Sub Push format: Valid JSON body with "message" -> "data" (base64)
    # Ref: https://cloud.google.com/pubsub/docs/push
    data_b64 = base64.b64encode(job_json.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": {
            "attriutes": {"key": "value"},
            "data": data_b64,
            "messageId": "1234567890"
        },
        "subscription": "projects/myproject/subscriptions/mysub"
    }
    
    print(f"Sending job for {args.repo} to {args.url}...")
    try:
        resp = requests.post(args.url, json=payload, headers={"Content-Type": "application/json"})
        print(f"Response Status: {resp.status_code}")
        print(f"Response Body: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
