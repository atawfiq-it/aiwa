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
from app.utils.safetensors_inspector import inspect_safetensors_type

logger = logging.getLogger(__name__)

STYLE_PRESETS = {
    "none": {"prompt": "{prompt}", "negative": ""},
    "cinematic": {
        "prompt": (
            "{prompt}, cinematic lighting, 8k resolution, photorealistic, "
            "blockbuster movie still, 35mm lens, sharp focus"
        ),
        "negative": (
            "cartoon, illustration, 3d render, anime, blurry, low resolution, bad anatomy"
        ),
    },
    "photorealistic": {
        "prompt": (
            "{prompt}, raw photo, ultra high resolution, highly detailed skin texture, "
            "professional portrait photography, dslr, soft natural lighting"
        ),
        "negative": (
            "painting, drawing, anime, cartoon, airbrushed, plastic skin, CGI, disfigured"
        ),
    },
    "digital_art": {
        "prompt": (
            "{prompt}, detailed digital painting, trending on artstation, masterpiece, "
            "intricate composition, vibrant color palette, dynamic lighting"
        ),
        "negative": "blurry, low quality, artifacts, watermark, grainy, deformed",
    },
    "anime": {
        "prompt": (
            "{prompt}, anime aesthetic, makoto shinkai style, studio ghibli, "
            "vibrant anime key visual, clean lineart, vibrant colors"
        ),
        "negative": "photorealistic, 3d, western comic, text, signature, low quality",
    },
    "fantasy": {
        "prompt": (
            "{prompt}, epic fantasy illustration, ethereal atmosphere, mystical glow, "
            "magical world, volumetric lighting, hyperdetailed"
        ),
        "negative": "modern, futuristic, photographic, low quality, ugly, blurry",
    },
}


class DirectDiffusionService:
    def list_checkpoints(self) -> list[dict[str, Any]]:
        """Deep recursive scan across configured .env paths for Diffusion checkpoints only."""
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
                        if not file_path.is_file():
                            continue

                        resolved_str = str(file_path.resolve())
                        if resolved_str in seen_paths:
                            continue

                        # Guard: Exclude MLX / LLM folders that contain tokenizer.json
                        parent_dir = file_path.parent
                        if (parent_dir / "tokenizer.json").exists() or (
                            parent_dir / "tokenizer_config.json"
                        ).exists():
                            continue

                        size_bytes = file_path.stat().st_size
                        # Filter out tiny adapter/LoRA files (< 500 MB)
                        if size_bytes <= 500 * 1024 * 1024:
                            continue

                        # Guard: Inspect binary header to verify this is a Diffusion model
                        if lower.endswith(".safetensors"):
                            if inspect_safetensors_type(file_path) != "diffusion":
                                continue

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
            pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
                config, use_karras_sigmas=True
            )

    def _get_compute_device(self) -> tuple[str, torch.dtype]:
        """Determines the optimal PyTorch device across CUDA, Apple MPS, or CPU."""
        if torch.cuda.is_available():
            return "cuda", torch.float16
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps", torch.float16
        return "cpu", torch.float32

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

        # Yield GPU memory from LLM if currently loaded
        if model_supervisor.process:
            logger.info("Yielding GPU from LLM to Direct Diffusion...")
            await model_supervisor.unload_model()

        device, torch_dtype = self._get_compute_device()

        # Apply Style Preset
        preset = STYLE_PRESETS.get(style_preset.lower(), STYLE_PRESETS["none"])
        final_prompt = preset["prompt"].format(prompt=prompt)
        combined_negative = f"{negative_prompt}, {preset['negative']}".strip(", ")

        # Configure deterministic seed
        if seed == -1:
            seed = int(torch.randint(0, 2**32 - 1, (1,)).item())

        # Note: MPS generator runs cleanly on CPU or MPS device depending on PyTorch build
        gen_device = "cpu" if device == "mps" else device
        generator = torch.Generator(device=gen_device).manual_seed(seed)

        logger.info(
            f"Loading checkpoint '{ckpt_file.name}' on {device.upper()} "
            f"(Sampler: {sampler}, Seed: {seed})..."
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

            self._configure_scheduler(pipeline, sampler)
            pipeline.to(device)

            if hasattr(pipeline, "vae") and hasattr(pipeline.vae, "enable_tiling"):
                pipeline.vae.enable_tiling()

            logger.info(
                f"Generating {batch_size} image(s) "
                f"({width}x{height}, {steps} steps, CFG {guidance_scale})..."
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

                    meta = (
                        f'{{"checkpoint": "{ckpt_file.name}", '
                        f'"steps": {steps}, "cfg": {guidance_scale}, '
                        f'"seed": {seed}, "sampler": "{sampler}"}}'
                    )

                    file_record = GeneratedFile(
                        file_type="image",
                        file_name=filename,
                        file_path=str(output_path.resolve()),
                        mime_type="image/png",
                        file_size_bytes=output_path.stat().st_size,
                        prompt=prompt,
                        metadata_json=meta,
                    )
                    db.add(file_record)
                    db.commit()
                    db.refresh(file_record)

                    generated_artifacts.append(
                        {
                            "file_id": file_record.id,
                            "file_name": filename,
                            "image_url": (
                                f"http://{settings.API_HOST}:{settings.API_PORT}"
                                f"/api/v1/media/files/{file_record.id}"
                            ),
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
            elif hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()


direct_diffusion = DirectDiffusionService()
