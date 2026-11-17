import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.database.engine import engine
from app.database.models import GeneratedFile
from app.supervisors.model_supervisor import model_supervisor

logger = logging.getLogger(__name__)


def torch_cuda_available() -> bool:
    """Checks if PyTorch has CUDA access for RNG device flag selection."""
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


class SDCppService:
    def __init__(self):
        self.sd_bin = settings.BASE_DIR / "services" / "diffusion-cpp" / "sd"

    def is_installed(self) -> bool:
        """Verifies if the compiled C++ executable is present on disk."""
        return self.sd_bin.exists()

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        checkpoint_path: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        guidance_scale: float = 7.0,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Executes the pure C++ stable-diffusion.cpp binary with dedicated GPU allocation."""
        if not self.is_installed():
            raise RuntimeError(
                "stable-diffusion.cpp is not installed. Run 'just install-sd-cpp' first."
            )

        ckpt_file = Path(checkpoint_path).resolve()
        if not ckpt_file.exists():
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_file}")

        # Yield GPU from LLM if loaded to prevent VRAM competition
        if model_supervisor.process:
            logger.info("Yielding GPU from LLM to stable-diffusion.cpp...")
            await model_supervisor.unload_model()

        gen_id = uuid.uuid4().hex[:8]
        output_prefix = str(settings.GENERATED_DIR / f"sd_cpp_{gen_id}")

        cmd = [
            str(self.sd_bin),
            "-m",
            str(ckpt_file),
            "-p",
            prompt,
            "-n",
            negative_prompt,
            "--width",
            str(width),
            "--height",
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
            f"{output_prefix}.png",
        ]

        logger.info(f"Executing sd.cpp binary: {' '.join(cmd)}")
        process = subprocess.run(cmd, capture_output=True, text=True)

        if process.returncode != 0:
            raise RuntimeError(f"sd.cpp execution failed: {process.stderr}")

        final_file = Path(f"{output_prefix}.png")
        if not final_file.exists():
            matches = list(settings.GENERATED_DIR.glob(f"*sd_cpp_{gen_id}*"))
            if matches:
                final_file = matches[0]
            else:
                raise FileNotFoundError("sd.cpp finished but output image file was not found.")

        file_size = final_file.stat().st_size

        # Persist generated artifact record in SQLite
        with Session(engine) as db:
            gen_file = GeneratedFile(
                file_type="image",
                file_name=final_file.name,
                file_path=str(final_file.resolve()),
                mime_type="image/png",
                file_size_bytes=file_size,
                prompt=prompt,
                metadata_json=f'{{"engine": "stable-diffusion.cpp", "steps": {steps}}}',
            )
            db.add(gen_file)
            db.commit()
            db.refresh(gen_file)
            file_id = gen_file.id

        logger.info(f"✅ stable-diffusion.cpp generated artifact: {final_file.name}")
        return {
            "file_id": file_id,
            "file_name": final_file.name,
            "image_url": f"http://127.0.0.1:8000/api/v1/media/files/{file_id}",
            "file_path": str(final_file.resolve()),
        }


sd_cpp_service = SDCppService()
