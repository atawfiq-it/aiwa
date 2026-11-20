import logging
import platform
import random
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.database.engine import engine
from app.database.models import GeneratedFile
from app.supervisors.model_supervisor import ModelState, model_supervisor

logger = logging.getLogger(__name__)


def torch_cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


class SDCppService:
    def __init__(self):
        bin_name = "sd.exe" if platform.system() == "Windows" else "sd"
        self.sd_bin = settings.BASE_DIR / "services" / "diffusion-cpp" / bin_name

    def is_installed(self) -> bool:
        return self.sd_bin.exists() and self.sd_bin.is_file()

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        checkpoint_path: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        guidance_scale: float = 7.0,
        seed: int = -1,
    ) -> dict[str, Any]:
        if model_supervisor.process or model_supervisor.state != ModelState.UNLOADED:
            logger.info("🔄 Process Change (LLM -> sd.cpp): Unloading LLM and keeping it unloaded.")
            await model_supervisor.unload_model()

        if not self.is_installed():
            raise RuntimeError(
                "stable-diffusion.cpp binary not found. Run 'just install-sd-cpp' first."
            )

        ckpt_file = Path(checkpoint_path).resolve()
        if not ckpt_file.exists():
            raise FileNotFoundError(f"Checkpoint not found at: {ckpt_file}")

        # Yield GPU from LLM if active
        if model_supervisor.process:
            logger.info("Yielding GPU from LLM to stable-diffusion.cpp...")
            await model_supervisor.unload_model()

        if seed == -1:
            seed = random.randint(0, 2**31 - 1)

        gen_id = uuid.uuid4().hex[:8]
        output_file = settings.GENERATED_DIR / f"sd_cpp_{gen_id}.png"

        cmd = [
            str(self.sd_bin),
            "-m",
            str(ckpt_file),
            "-p",
            prompt,
            "-n",
            negative_prompt,
            "-W",
            str(width),
            "-H",
            str(height),
            "--steps",
            str(steps),
            "--cfg-scale",
            str(guidance_scale),
            "--rng",
            "cuda" if torch_cuda_available() else "std_default",
            "-s",
            str(seed),
            "-o",
            str(output_file),
        ]

        logger.info(f"Executing stable-diffusion.cpp: {' '.join(cmd)}")
        process = subprocess.run(cmd, capture_output=True, text=True)

        if process.returncode != 0:
            raise RuntimeError(f"sd.cpp execution failed: {process.stderr}")

        final_file = output_file
        if not final_file.exists():
            matches = list(settings.GENERATED_DIR.glob(f"*sd_cpp_{gen_id}*"))
            if matches:
                final_file = matches[0]
            else:
                raise FileNotFoundError("sd.cpp finished but output image file was not found.")

        file_size = final_file.stat().st_size

        with Session(engine) as db:
            gen_file = GeneratedFile(
                file_type="image",
                file_name=final_file.name,
                file_path=str(final_file.resolve()),
                mime_type="image/png",
                file_size_bytes=file_size,
                prompt=prompt,
                metadata_json=(
                    f'{{"engine": "stable-diffusion.cpp", '
                    f'"checkpoint": "{ckpt_file.name}", '
                    f'"steps": {steps}, "seed": {seed}}}'
                ),
            )
            db.add(gen_file)
            db.commit()
            db.refresh(gen_file)
            file_id = gen_file.id

        image_url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/media/files/{file_id}"
        return {
            "file_id": file_id,
            "file_name": final_file.name,
            "image_url": image_url,
            "file_path": str(final_file.resolve()),
            "seed": seed,
        }


sd_cpp_service = SDCppService()
