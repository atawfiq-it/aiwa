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

STYLE_PRESETS = {
    "none": {"prompt": "{prompt}", "negative": ""},
    "cinematic": {
        "prompt": "{prompt}, cinematic lighting, 8k resolution, photorealistic, blockbuster movie still, 35mm lens, sharp focus",
        "negative": "cartoon, illustration, 3d render, anime, blurry, low resolution, bad anatomy",
    },
    "photorealistic": {
        "prompt": "{prompt}, raw photo, ultra high resolution, highly detailed skin texture, professional portrait photography, dslr, soft natural lighting",
        "negative": "painting, drawing, anime, cartoon, airbrushed, plastic skin, CGI, disfigured",
    },
    "digital_art": {
        "prompt": "{prompt}, detailed digital painting, trending on artstation, masterpiece, intricate composition, vibrant color palette, dynamic lighting",
        "negative": "blurry, low quality, artifacts, watermark, grainy, deformed",
    },
    "anime": {
        "prompt": "{prompt}, anime aesthetic, makoto shinkai style, studio ghibli, vibrant anime key visual, clean lineart, vibrant colors",
        "negative": "photorealistic, 3d, western comic, text, signature, low quality",
    },
    "fantasy": {
        "prompt": "{prompt}, epic fantasy illustration, ethereal atmosphere, mystical glow, magical world, volumetric lighting, hyperdetailed",
        "negative": "modern, futuristic, photographic, low quality, ugly, blurry",
    },
}


class DirectDiffusionService:
    def list_checkpoints(self) -> list[dict[str, Any]]:
        """Deep recursive scan across all directories configured in .env for .safetensors and .ckpt."""
        search_dirs = settings.get_diffusion_search_paths()
        discovered: list[dict[str, Any]] = []
        seen_paths = set()

        for base_dir in search_dirs:
            for root, _, files in os.walk(base_dir, followlinks=True):
                for f in files:
                    lower = f.lower()
                    if lower.endswith((".safetensors", ".ckpt")):
                        file_path = Path(root) / f
                        resolved_str = str(file_path.resolve())

                        if resolved_str in seen_paths:
                            continue

                        size_bytes = file_path.stat().st_size
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

    def _configure_scheduler(self, pipeline: Any, sampler_name: str) -> None:
        """Configures the user-selected high-quality scheduler."""
        from diffusers import (
            DDIMScheduler,
            DPMSolverMultistepScheduler,
            EulerAncestralDiscreteScheduler,
            EulerDiscreteScheduler,
        )

        config = pipeline.scheduler.config

        if sampler_name == "DPM++ 2M Karras":
            pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
                config, use_karras_sigmas=True, algorithm_type="dpmsolver++"
            )
        elif sampler_name == "Euler a":
            pipeline.scheduler = EulerAncestralDiscreteScheduler.from_config(config)
        elif sampler_name == "Euler":
            pipeline.scheduler = EulerDiscreteScheduler.from_config(config)
        elif sampler_name == "DDIM":
            pipeline.scheduler = DDIMScheduler.from_config(config)
        else:
            # Default to DPM++ 2M Karras (standard for SD)
            pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
                config, use_karras_sigmas=True
            )

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        checkpoint_path: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 25,
        guidance_scale: float = 7.0,
        sampler: str = "DPM++ 2M Karras",
        seed: int = -1,
        batch_size: int = 1,
        style_preset: str = "none",
    ) -> dict[str, Any]:
        ckpt_file = Path(checkpoint_path).resolve()
        if not ckpt_file.exists():
            raise FileNotFoundError(f"Checkpoint not found at: {ckpt_file}")

        # Yield GPU from LLM if active
        if model_supervisor.process:
            logger.info("Yielding GPU from LLM to Direct Diffusion...")
            await model_supervisor.unload_model()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if device == "cuda" else torch.float32

        # Apply Style Preset
        preset = STYLE_PRESETS.get(style_preset.lower(), STYLE_PRESETS["none"])
        final_prompt = preset["prompt"].format(prompt=prompt)
        combined_negative = f"{negative_prompt}, {preset['negative']}".strip(", ")

        # Configure deterministic seed
        if seed == -1:
            seed = torch.randint(0, 2**32 - 1, (1,)).item()
        generator = torch.Generator(device=device).manual_seed(seed)

        logger.info(
            f"Loading checkpoint '{ckpt_file.name}' on {device} (Sampler: {sampler}, Seed: {seed})..."
        )
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

            # Apply Sampler
            self._configure_scheduler(pipeline, sampler)
            pipeline.to(device)

            # Prevent black images / numerical NaN on half-precision VAE
            if hasattr(pipeline, "vae") and hasattr(pipeline.vae, "enable_tiling"):
                pipeline.vae.enable_tiling()

            logger.info(
                f"Generating {batch_size} image(s) ({width}x{height}, {steps} steps, CFG {guidance_scale})..."
            )
            result = pipeline(
                prompt=[final_prompt] * batch_size,
                negative_prompt=[combined_negative] * batch_size if combined_negative else None,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )

            generated_artifacts = []
            with Session(engine) as db:
                for img in result.images:
                    filename = f"art_{uuid.uuid4().hex[:8]}.png"
                    output_path = settings.GENERATED_DIR / filename
                    img.save(output_path)

                    file_record = GeneratedFile(
                        file_type="image",
                        file_name=filename,
                        file_path=str(output_path.resolve()),
                        mime_type="image/png",
                        file_size_bytes=output_path.stat().st_size,
                        prompt=prompt,
                        metadata_json=f'{{"checkpoint": "{ckpt_file.name}", "steps": {steps}, "cfg": {guidance_scale}, "seed": {seed}, "sampler": "{sampler}"}}',
                    )
                    db.add(file_record)
                    db.commit()
                    db.refresh(file_record)

                    generated_artifacts.append(
                        {
                            "file_id": file_record.id,
                            "file_name": filename,
                            "image_url": f"http://127.0.0.1:8000/api/v1/media/files/{file_record.id}",
                        }
                    )

            return {
                "artifacts": generated_artifacts,
                "seed": seed,
                "steps": steps,
                "sampler": sampler,
                "cfg": guidance_scale,
            }

        finally:
            del pipeline
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


direct_diffusion = DirectDiffusionService()
