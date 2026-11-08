import gc
import logging
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
        """Scans for available .safetensors files in data/models and custom directories."""
        from app.services.models.scanner import model_scanner

        # Scan models directory
        models = model_scanner.scan_directories([str(settings.MODELS_DIR.resolve())])
        checkpoints = []

        for m in models:
            if m.get("category") == "diffusion" or m["file_path"].endswith(
                (".safetensors", ".ckpt")
            ):
                checkpoints.append(
                    {
                        "name": m["display_name"],
                        "path": m["file_path"],
                        "size_gb": m.get("file_size_gb", 0),
                    }
                )
        return checkpoints

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
