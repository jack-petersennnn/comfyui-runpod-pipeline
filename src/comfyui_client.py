"""
ComfyUI WebSocket API client.

Manages workflow execution through ComfyUI's native API, handling
prompt queuing, progress tracking, and result retrieval.
"""

import io
import json
import time
import uuid
import logging
from urllib.parse import urlencode

import requests
import websocket

logger = logging.getLogger("comfyui_client")

EXECUTION_TIMEOUT = 300  # 5 minutes max per workflow


class ComfyUIClient:
    """Client for ComfyUI's HTTP + WebSocket API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws"
        self.client_id = str(uuid.uuid4())

    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Poll ComfyUI's system stats endpoint until responsive."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
                if resp.status_code == 200:
                    return True
            except requests.ConnectionError:
                pass
            time.sleep(2)
        return False

    def execute_workflow(self, workflow: dict, job_id: str) -> list[bytes]:
        """
        Queue a workflow and wait for completion.

        Returns a list of output image bytes.
        """
        prompt_id = self._queue_prompt(workflow)
        logger.info("Queued prompt %s for job %s", prompt_id, job_id)

        # Connect via WebSocket to track execution
        ws = websocket.create_connection(
            f"{self.ws_url}?{urlencode({'clientId': self.client_id})}",
            timeout=EXECUTION_TIMEOUT,
        )

        try:
            output_images = self._wait_for_completion(ws, prompt_id)
        finally:
            ws.close()

        return output_images

    def _queue_prompt(self, workflow: dict) -> str:
        """Submit a workflow to ComfyUI's prompt queue."""
        payload = {
            "prompt": workflow,
            "client_id": self.client_id,
        }

        resp = requests.post(
            f"{self.base_url}/prompt",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()

        data = resp.json()
        return data["prompt_id"]

    def _wait_for_completion(self, ws: websocket.WebSocket, prompt_id: str) -> list[bytes]:
        """
        Listen on WebSocket for execution progress and completion.

        Returns output images once the prompt finishes executing.
        """
        start = time.time()

        while time.time() - start < EXECUTION_TIMEOUT:
            raw = ws.recv()
            if isinstance(raw, bytes):
                # Binary frame = preview image, skip
                continue

            msg = json.loads(raw)
            msg_type = msg.get("type")
            msg_data = msg.get("data", {})

            if msg_type == "executing":
                if msg_data.get("prompt_id") == prompt_id and msg_data.get("node") is None:
                    # Execution complete
                    logger.info("Prompt %s execution complete", prompt_id)
                    return self._fetch_outputs(prompt_id)

            elif msg_type == "execution_error":
                if msg_data.get("prompt_id") == prompt_id:
                    node_id = msg_data.get("node_id", "unknown")
                    error_msg = msg_data.get("exception_message", "Unknown error")
                    raise RuntimeError(
                        f"ComfyUI execution error in node {node_id}: {error_msg}"
                    )

            elif msg_type == "progress":
                if msg_data.get("prompt_id") == prompt_id:
                    value = msg_data.get("value", 0)
                    max_val = msg_data.get("max", 0)
                    if max_val > 0:
                        logger.debug("Progress: %d/%d", value, max_val)

        raise TimeoutError(f"Workflow execution exceeded {EXECUTION_TIMEOUT}s timeout")

    def _fetch_outputs(self, prompt_id: str) -> list[bytes]:
        """Retrieve output images from ComfyUI's history."""
        resp = requests.get(
            f"{self.base_url}/history/{prompt_id}",
            timeout=30,
        )
        resp.raise_for_status()

        history = resp.json()
        prompt_history = history.get(prompt_id, {})
        outputs = prompt_history.get("outputs", {})

        images: list[bytes] = []

        for node_id, node_output in outputs.items():
            for image_info in node_output.get("images", []):
                filename = image_info["filename"]
                subfolder = image_info.get("subfolder", "")
                img_type = image_info.get("type", "output")

                params = urlencode({
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": img_type,
                })

                img_resp = requests.get(
                    f"{self.base_url}/view?{params}",
                    timeout=30,
                )
                img_resp.raise_for_status()
                images.append(img_resp.content)

        return images
