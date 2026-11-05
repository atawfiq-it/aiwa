import asyncio
import json
import logging
import uuid
from typing import Any

import httpx
from sqlmodel import Session

from app.core.config import settings
from app.database.models import GeneratedFile, Task
from app.services.tasks.queue import register_task_handler

logger = logging.getLogger(__name__)


class ComfyUIAdapter:
    def __init__(self):
        self.base_url = settings.COMFYUI_BASE_URL

    async def is_available(self) -> bool:
        """Check if ComfyUI service is running and accessible."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/system_stats")
                return res.status_code == 200
        except Exception:
            return False

    def build_default_txt2img_workflow(
        self,
        prompt: str,
        negative_prompt: str = "ugly, blurry, distorted",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
    ) -> dict[str, Any]:
        """Build standard ComfyUI prompt dictionary for SD1.5 / SDXL checkpoints."""
        client_id = str(uuid.uuid4())
        return {
            "client_id": client_id,
            "prompt": {
                "3": {
                    "class_type": "KSampler",
                    "inputs": {
                        "cfg": 8,
                        "denoise": 1,
                        "latent_image": ["5", 0],
                        "model": ["4", 0],
                        "negative": ["7", 0],
                        "positive": ["6", 0],
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "seed": 42,
                        "steps": steps,
                    },
                },
                "4": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
                },
                "5": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"batch_size": 1, "height": height, "width": width},
                },
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["4", 1], "text": prompt},
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["4", 1], "text": negative_prompt},
                },
                "8": {
                    "class_type": "VAEDecode",
                    "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                },
                "9": {
                    "class_type": "SaveImage",
                    "inputs": {"filename_prefix": "AIWA", "images": ["8", 0]},
                },
            },
        }

    async def execute_workflow(
        self,
        prompt: str,
        negative_prompt: str = "ugly, blurry, distorted",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
    ) -> dict[str, Any]:
        if not await self.is_available():
            raise RuntimeError(
                f"ComfyUI is not reachable at {self.base_url}. Ensure ComfyUI service is running."
            )

        workflow_data = self.build_default_txt2img_workflow(
            prompt, negative_prompt, width, height, steps
        )

        async with httpx.AsyncClient(timeout=180.0) as client:
            res = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow_data["prompt"]},
            )
            if res.status_code != 200:
                raise RuntimeError(f"ComfyUI rejected prompt: {res.text}")

            prompt_id = res.json().get("prompt_id")

            # Poll for completion in ComfyUI history
            for _ in range(120):
                await asyncio.sleep(1.5)
                hist_res = await client.get(f"{self.base_url}/history/{prompt_id}")
                if hist_res.status_code == 200:
                    hist_data = hist_res.json()
                    if prompt_id in hist_data:
                        outputs = hist_data[prompt_id].get("outputs", {})
                        save_node = outputs.get("9", {})
                        images = save_node.get("images", [])
                        if images:
                            img_info = images[0]
                            img_res = await client.get(
                                f"{self.base_url}/view",
                                params={
                                    "filename": img_info["filename"],
                                    "subfolder": img_info.get("subfolder", ""),
                                    "type": img_info.get("type", "output"),
                                },
                            )
                            saved_path = settings.GENERATED_DIR / img_info["filename"]
                            with open(saved_path, "wb") as f:
                                f.write(img_res.content)

                            return {
                                "file_name": img_info["filename"],
                                "file_path": str(saved_path),
                                "file_size_bytes": saved_path.stat().st_size,
                                "mime_type": "image/png",
                            }

            raise TimeoutError("Timed out waiting for ComfyUI image rendering")


comfyui_adapter = ComfyUIAdapter()


# In backend/app/services/media/comfyui.py:


@register_task_handler("image_generation")
async def handle_image_generation(task: Task, db: Session) -> dict[str, Any]:
    """Worker task handler with Dynamic VRAM Swap Interlock."""
    from app.supervisors.comfyui_supervisor import comfyui_supervisor
    from app.supervisors.model_supervisor import model_supervisor

    params = json.loads(task.parameters)
    prompt = params.get("prompt", "")
    negative_prompt = params.get("negative_prompt", "ugly, blurry, bad anatomy")
    # checkpoint = params.get("checkpoint", "dreamshaper_8.safetensors")
    steps = params.get("steps", 4)
    width = params.get("width", 512)
    height = params.get("height", 512)

    # 1. Acquire supervisor lock to avoid simultaneous LLM inference
    async with model_supervisor.lock:
        active_llm = model_supervisor.active_model
        if active_llm and model_supervisor.process:
            logger.info("🔄 VRAM Interlock: Temporarily yielding GPU memory from LLM to ComfyUI...")
            await model_supervisor._stop_process()

        try:
            # 2. Ensure embedded ComfyUI is up
            await comfyui_supervisor.ensure_running()

            # 3. Execute diffusion workflow
            result = await comfyui_adapter.execute_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
            )
        finally:
            # 4. Restore LLM back to GPU
            if active_llm:
                logger.info(f"🔄 VRAM Interlock: Restoring '{active_llm.display_name}' to GPU...")
                try:
                    await model_supervisor.load_model(active_llm)
                except Exception as e:
                    logger.error(f"Failed restoring LLM after image generation: {e}")

    # 5. Record generated artifact in database
    gen_file = GeneratedFile(
        task_id=task.id,
        file_type="image",
        file_name=result["file_name"],
        file_path=result["file_path"],
        mime_type=result["mime_type"],
        file_size_bytes=result["file_size_bytes"],
        prompt=prompt,
        metadata_json=task.parameters,
    )
    db.add(gen_file)
    db.commit()
    db.refresh(gen_file)

    result["file_id"] = gen_file.id
    return result
