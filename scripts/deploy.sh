#!/usr/bin/env bash
set -euo pipefail

# Deploy ComfyUI handler to RunPod Serverless
#
# Required environment variables:
#   RUNPOD_API_KEY    - RunPod API key
#   DOCKER_IMAGE      - Full image path (e.g., dockerhub-user/comfyui-runpod:latest)
#
# Optional:
#   ENDPOINT_NAME     - Name for the endpoint (default: comfyui-pipeline)
#   GPU_TYPE          - GPU type ID (default: NVIDIA RTX A5000)
#   MIN_WORKERS       - Minimum workers (default: 0)
#   MAX_WORKERS       - Maximum workers (default: 3)
#   IDLE_TIMEOUT      - Idle timeout in seconds (default: 60)

ENDPOINT_NAME="${ENDPOINT_NAME:-comfyui-pipeline}"
GPU_TYPE="${GPU_TYPE:-NVIDIA RTX A5000}"
MIN_WORKERS="${MIN_WORKERS:-0}"
MAX_WORKERS="${MAX_WORKERS:-3}"
IDLE_TIMEOUT="${IDLE_TIMEOUT:-60}"

if [[ -z "${RUNPOD_API_KEY:-}" ]]; then
    echo "Error: RUNPOD_API_KEY is required" >&2
    exit 1
fi

if [[ -z "${DOCKER_IMAGE:-}" ]]; then
    echo "Error: DOCKER_IMAGE is required" >&2
    exit 1
fi

echo "Creating RunPod serverless endpoint: ${ENDPOINT_NAME}"
echo "  Image:       ${DOCKER_IMAGE}"
echo "  GPU:         ${GPU_TYPE}"
echo "  Workers:     ${MIN_WORKERS}-${MAX_WORKERS}"
echo "  Idle timeout: ${IDLE_TIMEOUT}s"

RESPONSE=$(curl -s -X POST "https://api.runpod.io/v2/endpoints" \
    -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"${ENDPOINT_NAME}\",
        \"templateId\": null,
        \"dockerImage\": \"${DOCKER_IMAGE}\",
        \"gpuIds\": \"${GPU_TYPE}\",
        \"workersMin\": ${MIN_WORKERS},
        \"workersMax\": ${MAX_WORKERS},
        \"idleTimeout\": ${IDLE_TIMEOUT},
        \"env\": {
            \"S3_BUCKET\": \"${S3_BUCKET:-}\",
            \"S3_ACCESS_KEY\": \"${S3_ACCESS_KEY:-}\",
            \"S3_SECRET_KEY\": \"${S3_SECRET_KEY:-}\",
            \"S3_ENDPOINT\": \"${S3_ENDPOINT:-}\",
            \"S3_REGION\": \"${S3_REGION:-auto}\"
        },
        \"volumeInGb\": 50,
        \"containerDiskInGb\": 30
    }")

ENDPOINT_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

if [[ -n "$ENDPOINT_ID" ]]; then
    echo ""
    echo "Endpoint created successfully!"
    echo "  Endpoint ID: ${ENDPOINT_ID}"
    echo "  API URL:     https://api.runpod.ai/v2/${ENDPOINT_ID}"
    echo ""
    echo "Test with:"
    echo "  python scripts/test_endpoint.py --endpoint-id ${ENDPOINT_ID} --api-key \${RUNPOD_API_KEY}"
else
    echo "Error creating endpoint:" >&2
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE" >&2
    exit 1
fi
