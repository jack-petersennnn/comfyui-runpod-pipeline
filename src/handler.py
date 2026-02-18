"""
RunPod Serverless Handler for ComfyUI workflows.

Accepts workflow requests, executes them through ComfyUI's API,
and uploads results to S3-compatible storage.
"""

import os
import sys
import time
import subprocess
import threading
import logging

import runpod

from comfyui_client import ComfyUIClient
from workflow_loader import WorkflowLoader
from storage import StorageClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("handler")

COMFYUI_PATH = os.environ.get("COMFYUI_PATH", "/opt/comfyui")
COMFYUI_PORT = int(os.environ.get("COMFYUI_PORT", "8188"))
WORKFLOW_DIR = os.environ.get("WORKFLOW_DIR", "/opt/handler/workflows")

comfyui_process: subprocess.Popen | None = None


def start_comfyui() -> None:
    """Launch ComfyUI as a background process and wait for it to be ready."""
    global comfyui_process

    logger.info("Starting ComfyUI server on port %d", COMFYUI_PORT)

    comfyui_process = subprocess.Popen(
        [
            sys.executable, "main.py",
            "--listen", "127.0.0.1",
            "--port", str(COMFYUI_PORT),
            "--disable-auto-launch",
        ],
        cwd=COMFYUI_PATH,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Stream ComfyUI logs in background
    def stream_logs():
        assert comfyui_process and comfyui_process.stdout
        for line in comfyui_process.stdout:
            logger.debug("[ComfyUI] %s", line.decode().rstrip())

    log_thread = threading.Thread(target=stream_logs, daemon=True)
    log_thread.start()

    # Wait for ComfyUI to become responsive
    client = ComfyUIClient(port=COMFYUI_PORT)
    if not client.wait_for_ready(timeout=120):
        raise RuntimeError("ComfyUI failed to start within timeout")

    logger.info("ComfyUI is ready")


def validate_input(job_input: dict) -> tuple[bool, str]:
    """Validate the incoming job input."""
    workflow_type = job_input.get("workflow_type")
    if not workflow_type:
        return False, "Missing required field: workflow_type"

    valid_types = {"image_gen", "face_swap"}
    if workflow_type not in valid_types:
        return False, f"Invalid workflow_type '{workflow_type}'. Must be one of: {valid_types}"

    if workflow_type == "image_gen":
        if not job_input.get("prompt"):
            return False, "image_gen requires 'prompt' field"

    if workflow_type == "face_swap":
        if not job_input.get("source_image"):
            return False, "face_swap requires 'source_image' field"
        if not job_input.get("target_image"):
            return False, "face_swap requires 'target_image' field"

    return True, ""


def handler(job: dict) -> dict:
    """
    RunPod serverless handler entry point.

    Accepts a job dict with 'input' containing workflow parameters,
    executes the workflow through ComfyUI, and returns output URLs.
    """
    job_input = job.get("input", {})
    job_id = job.get("id", "unknown")

    logger.info("Processing job %s: workflow_type=%s", job_id, job_input.get("workflow_type"))

    # Validate
    valid, error = validate_input(job_input)
    if not valid:
        return {"error": error}

    workflow_type = job_input["workflow_type"]

    try:
        # Load and parameterize workflow
        loader = WorkflowLoader(WORKFLOW_DIR)
        workflow = loader.load(workflow_type, job_input)

        # Execute through ComfyUI
        client = ComfyUIClient(port=COMFYUI_PORT)
        output_images = client.execute_workflow(workflow, job_id)

        if not output_images:
            return {"error": "Workflow produced no output images"}

        # Upload results to storage
        storage = StorageClient()
        urls = []
        for i, image_data in enumerate(output_images):
            key = f"outputs/{job_id}/{workflow_type}_{i}.png"
            url = storage.upload(image_data, key, content_type="image/png")
            urls.append(url)
            logger.info("Uploaded result %d: %s", i, key)

        return {
            "status": "success",
            "output_urls": urls,
            "workflow_type": workflow_type,
            "job_id": job_id,
        }

    except TimeoutError:
        logger.error("Job %s timed out during execution", job_id)
        return {"error": "Workflow execution timed out"}
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        return {"error": str(e)}


# Start ComfyUI before accepting jobs
start_comfyui()

runpod.serverless.start({"handler": handler})
