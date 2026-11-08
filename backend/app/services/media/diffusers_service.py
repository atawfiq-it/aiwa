import gc
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import torch
from sqlmodel import Session

from app.core.config import settings
from app.database.engine import engine
from app.database.models import GeneratedFile
from app.supervisors.model_supervisor import model_supervisor

logger = logging.getLogger(__name__)


class DirectDiffusionService:
    def list_checkpoints(self) -> list[dict[str, Any]]:
        """Deep recursive scan across all directories configured in .env for .safetensors and .ckpt."""
        search_dirs = settings.get_diffusion_search_paths()
        discovered: list[dict[str, Any]] = []
        seen_paths = set()

        for base_dir in search_dirs:
            logger.info(f"Scanning for diffusion checkpoints in: {base_dir}")
            for root, _, files in os.walk(base_dir, followlinks=True):
                for f in files:
                    lower = f.lower()
                    if lower.endswith((".safetensors", ".ckpt")):
                        file_path = Path(root) / f
                        resolved_str = str(file_path.resolve())

                        if resolved_str in seen_paths:
                            continue

                        size_bytes = file_path.stat().st_size
                        # Filter out tiny adapter/LoRA files (< 500 MB)
                        if size_bytes > 500 * 1024 * 1024:
                            seen_paths.add(resolved_str)
                            discovered.append(
                                {
                                    "name": file_path.stem.replace("_", " "),
                                    "filename": f,
                                    "path": resolved_str,
                                    "size_gb": round(size_bytes / (1024**3), 2),
                                    "folder": str(Path(root).name),
                                }
                            )

        return sorted(discovered, key=lambda x: x["name"])

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "ugly, blurry, bad anatomy, low quality",
        checkpoint_path: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 4,
        guidance_scale: float = 1.5,
    ) -> dict[str, Any]:
        """Generates image directly on GPU using diffusers pipeline."""
        ckpt_file = Path(checkpoint_path).resolve()
        if not ckpt_file.exists():
            raise FileNotFoundError(f"Checkpoint not found at: {ckpt_file}")

        # 1. Unload LLM to give 100% of GPU to diffusion
        if model_supervisor.process:
            logger.info("Yielding GPU from LLM to Direct Diffusion...")
            await model_supervisor.unload_model()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if device == "cuda" else torch.float32

        logger.info(f"Loading checkpoint {ckpt_file.name} onto {device} (FP16)...")

        # Detect SDXL vs SD 1.5
        is_sdxl = any(k in ckpt_file.name.lower() for k in ["xl", "turbo", "lightning"])

        pipeline = None
        try:
            if is_sdxl:
                from diffusers import StableDiffusionXLPipeline

                pipeline = StableDiffusionXLPipeline.from_single_file(
                    str(ckpt_file),
                    torch_dtype=torch_dtype,
                    use_safetensors=True,
                )
            else:
                from diffusers import StableDiffusionPipeline

                pipeline = StableDiffusionPipeline.from_single_file(
                    str(ckpt_file),
                    torch_dtype=torch_dtype,
                    use_safetensors=True,
                )

            pipeline.to(device)

            # Generate
            logger.info(
                f"Generating image ({width}x{height}, {steps} steps, cfg {guidance_scale})..."
            )
            result = pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
            )

            image = result.images[0]

            # Save Output
            filename = f"art_{uuid.uuid4().hex[:8]}.png"
            output_path = settings.GENERATED_DIR / filename
            image.save(output_path)

            file_size = output_path.stat().st_size

            # Record in SQLite
            with Session(engine) as db:
                gen_file = GeneratedFile(
                    file_type="image",
                    file_name=filename,
                    file_path=str(output_path.resolve()),
                    mime_type="image/png",
                    file_size_bytes=file_size,
                    prompt=prompt,
                    metadata_json=f'{{"checkpoint": "{ckpt_file.name}", "steps": {steps}}}',
                )
                db.add(gen_file)
                db.commit()
                db.refresh(gen_file)
                file_id = gen_file.id

            logger.info(f"✅ Image generated successfully: {filename}")
            return {
                "file_id": file_id,
                "file_name": filename,
                "image_url": f"http://127.0.0.1:8000/api/v1/media/files/{file_id}",
                "file_path": str(output_path.resolve()),
            }

        finally:
            # Clean VRAM memory
            del pipeline
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


direct_diffusion = DirectDiffusionService()
