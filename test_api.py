"""Test script for the ingestion API endpoint."""

import requests
import json

# API endpoint URL
API_URL = "http://localhost:8000"

def test_health():
    """Test the health check endpoint."""
    print("Testing /health endpoint...")
    response = requests.get(f"{API_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_ingest_s3(bucket: str, key: str):
    """Test the S3 ingestion endpoint."""
    print(f"Testing /ingest/s3 endpoint with s3://{bucket}/{key}...")
    
    payload = {
        "bucket": bucket,
        "key": key,
        "chunk_size": 1000,
        "chunk_overlap": 200
    }
    
    try:
        response = requests.post(
            f"{API_URL}/ingest/s3",
            json=payload,
            timeout=300  # 5 minute timeout for large PDFs
        )
        response.raise_for_status()
        result = response.json()
        print(f"✅ Success!")
        print(f"Response: {json.dumps(result, indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")

if __name__ == "__main__":
    import sys
    
    # Test health endpoint
    test_health()
    
    # Test S3 ingestion if bucket and key provided
    if len(sys.argv) >= 3:
        bucket = sys.argv[1]
        key = sys.argv[2]
        test_ingest_s3(bucket, key)
    else:
        print("Usage:")
        print("  python test_api.py <bucket> <key>")
        print("\nExample:")
        print("  python test_api.py my-bucket path/to/document.pdf")
        print("\nOr test health endpoint only:")
        print("  python test_api.py")

