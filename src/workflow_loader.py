"""
Workflow template loader and parameter injection.

Loads ComfyUI workflow JSON templates and injects runtime parameters
(prompts, dimensions, seeds, image URLs) into the appropriate nodes.
"""

import json
import os
import logging
import random
from pathlib import Path

import requests

logger = logging.getLogger("workflow_loader")

WORKFLOW_MAP = {
    "image_gen": "flux_image_gen.json",
    "face_swap": "face_swap.json",
}


class WorkflowLoader:
    """Loads and parameterizes ComfyUI workflow templates."""

    def __init__(self, workflow_dir: str):
        self.workflow_dir = Path(workflow_dir)

    def load(self, workflow_type: str, params: dict) -> dict:
        """
        Load a workflow template and inject parameters.

        Args:
            workflow_type: One of 'image_gen' or 'face_swap'
            params: Runtime parameters to inject into the workflow

        Returns:
            Parameterized ComfyUI workflow dict ready for execution
        """
        filename = WORKFLOW_MAP.get(workflow_type)
        if not filename:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        template_path = self.workflow_dir / filename
        if not template_path.exists():
            raise FileNotFoundError(f"Workflow template not found: {template_path}")

        with open(template_path) as f:
            workflow = json.load(f)

        if workflow_type == "image_gen":
            return self._inject_image_gen(workflow, params)
        elif workflow_type == "face_swap":
            return self._inject_face_swap(workflow, params)

        return workflow

    def _inject_image_gen(self, workflow: dict, params: dict) -> dict:
        """Inject parameters into the FLUX image generation workflow."""
        prompt = params["prompt"]
        negative = params.get("negative_prompt", "blurry, low quality, watermark, text")
        width = params.get("width", 1280)
        height = params.get("height", 720)
        seed = params.get("seed", random.randint(0, 2**32 - 1))
        steps = params.get("steps", 25)
        cfg_scale = params.get("cfg_scale", 7.5)

        # Inject into CLIP Text Encode (positive prompt) — node "3"
        if "3" in workflow:
            workflow["3"]["inputs"]["text"] = prompt

        # Inject into CLIP Text Encode (negative prompt) — node "4"
        if "4" in workflow:
            workflow["4"]["inputs"]["text"] = negative

        # Inject into Empty Latent Image — node "5"
        if "5" in workflow:
            workflow["5"]["inputs"]["width"] = width
            workflow["5"]["inputs"]["height"] = height
            workflow["5"]["inputs"]["batch_size"] = 1

        # Inject into KSampler — node "6"
        if "6" in workflow:
            workflow["6"]["inputs"]["seed"] = seed
            workflow["6"]["inputs"]["steps"] = steps
            workflow["6"]["inputs"]["cfg"] = cfg_scale

        logger.info(
            "Injected image_gen params: %dx%d, %d steps, seed=%d",
            width, height, steps, seed,
        )
        return workflow

    def _inject_face_swap(self, workflow: dict, params: dict) -> dict:
        """Inject parameters into the face swap workflow."""
        source_url = params["source_image"]
        target_url = params["target_image"]
        face_index = params.get("face_index", 0)
        restore_face = params.get("restore_face", True)

        # Download source and target images to ComfyUI input directory
        input_dir = os.environ.get("COMFYUI_PATH", "/opt/comfyui") + "/input"
        os.makedirs(input_dir, exist_ok=True)

        source_path = self._download_image(source_url, input_dir, "source_face")
        target_path = self._download_image(target_url, input_dir, "target_image")

        # Inject source image path — node "1" (LoadImage for source face)
        if "1" in workflow:
            workflow["1"]["inputs"]["image"] = os.path.basename(source_path)

        # Inject target image path — node "2" (LoadImage for target)
        if "2" in workflow:
            workflow["2"]["inputs"]["image"] = os.path.basename(target_path)

        # Inject ReActor parameters — node "10"
        if "10" in workflow:
            workflow["10"]["inputs"]["input_faces_index"] = str(face_index)
            workflow["10"]["inputs"]["console_log_level"] = 1
            if not restore_face:
                workflow["10"]["inputs"]["face_restore_model"] = "none"

        logger.info("Injected face_swap params: face_index=%d, restore=%s", face_index, restore_face)
        return workflow

    def _download_image(self, url: str, dest_dir: str, prefix: str) -> str:
        """Download an image from URL to ComfyUI's input directory."""
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "image/png")
        ext = "jpg" if "jpeg" in content_type else "png"
        filename = f"{prefix}_{hash(url) & 0xFFFFFFFF:08x}.{ext}"
        filepath = os.path.join(dest_dir, filename)

        with open(filepath, "wb") as f:
            f.write(resp.content)

        logger.info("Downloaded %s → %s (%d bytes)", url[:80], filename, len(resp.content))
        return filepath
