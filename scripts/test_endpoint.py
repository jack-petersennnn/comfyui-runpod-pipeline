#!/usr/bin/env python3
"""
Smoke test for the deployed ComfyUI RunPod endpoint.

Usage:
    python test_endpoint.py --endpoint-id abc123 --api-key rp_xxxxx
"""

import argparse
import json
import sys
import time

import requests


def test_image_gen(base_url: str, headers: dict) -> bool:
    """Test the image generation workflow."""
    print("\n--- Testing image_gen workflow ---")

    payload = {
        "input": {
            "workflow_type": "image_gen",
            "prompt": "Modern luxury kitchen with marble countertops, warm natural lighting, professional real estate photography, 8K, ultra detailed",
            "negative_prompt": "blurry, low quality, watermark, text, cartoon",
            "width": 1280,
            "height": 720,
            "steps": 20,
            "seed": 12345,
        }
    }

    print(f"Submitting job...")
    resp = requests.post(f"{base_url}/runsync", json=payload, headers=headers, timeout=300)

    if resp.status_code != 200:
        print(f"  FAILED: HTTP {resp.status_code}")
        print(f"  {resp.text[:500]}")
        return False

    result = resp.json()
    status = result.get("status")

    if status == "COMPLETED":
        output = result.get("output", {})
        urls = output.get("output_urls", [])
        print(f"  Status: {output.get('status')}")
        print(f"  Output URLs: {len(urls)}")
        for url in urls:
            print(f"    → {url[:100]}...")
        return True
    else:
        print(f"  FAILED: status={status}")
        print(f"  Error: {result.get('output', {}).get('error', 'unknown')}")
        return False


def test_face_swap(base_url: str, headers: dict) -> bool:
    """Test the face swap workflow."""
    print("\n--- Testing face_swap workflow ---")

    payload = {
        "input": {
            "workflow_type": "face_swap",
            "source_image": "https://example.com/agent-headshot.jpg",
            "target_image": "https://example.com/generated-presenter.png",
            "face_index": 0,
            "restore_face": True,
        }
    }

    print("Submitting job...")
    resp = requests.post(f"{base_url}/run", json=payload, headers=headers, timeout=30)

    if resp.status_code != 200:
        print(f"  FAILED: HTTP {resp.status_code}")
        return False

    job_id = resp.json().get("id")
    print(f"  Job ID: {job_id}")

    # Poll for completion
    for attempt in range(60):
        time.sleep(5)
        status_resp = requests.get(f"{base_url}/status/{job_id}", headers=headers, timeout=30)
        status_data = status_resp.json()
        status = status_data.get("status")
        print(f"  Poll {attempt + 1}: {status}")

        if status == "COMPLETED":
            output = status_data.get("output", {})
            urls = output.get("output_urls", [])
            print(f"  Output URLs: {len(urls)}")
            return True
        elif status in ("FAILED", "CANCELLED"):
            print(f"  Error: {status_data.get('output', {}).get('error')}")
            return False

    print("  TIMED OUT waiting for completion")
    return False


def test_validation(base_url: str, headers: dict) -> bool:
    """Test input validation."""
    print("\n--- Testing input validation ---")

    # Missing workflow_type
    resp = requests.post(
        f"{base_url}/runsync",
        json={"input": {"prompt": "test"}},
        headers=headers,
        timeout=30,
    )
    result = resp.json().get("output", {})
    if "error" in result and "workflow_type" in result["error"]:
        print("  Missing workflow_type: correctly rejected ✓")
    else:
        print("  Missing workflow_type: unexpected response ✗")
        return False

    # Invalid workflow_type
    resp = requests.post(
        f"{base_url}/runsync",
        json={"input": {"workflow_type": "nonexistent"}},
        headers=headers,
        timeout=30,
    )
    result = resp.json().get("output", {})
    if "error" in result:
        print("  Invalid workflow_type: correctly rejected ✓")
    else:
        print("  Invalid workflow_type: unexpected response ✗")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Test ComfyUI RunPod endpoint")
    parser.add_argument("--endpoint-id", required=True, help="RunPod endpoint ID")
    parser.add_argument("--api-key", required=True, help="RunPod API key")
    parser.add_argument("--skip-generation", action="store_true", help="Skip actual generation tests")
    args = parser.parse_args()

    base_url = f"https://api.runpod.ai/v2/{args.endpoint_id}"
    headers = {"Authorization": f"Bearer {args.api_key}"}

    print(f"Testing endpoint: {base_url}")

    results = []

    results.append(("Validation", test_validation(base_url, headers)))

    if not args.skip_generation:
        results.append(("Image Gen", test_image_gen(base_url, headers)))
        results.append(("Face Swap", test_face_swap(base_url, headers)))

    print("\n=== Results ===")
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
