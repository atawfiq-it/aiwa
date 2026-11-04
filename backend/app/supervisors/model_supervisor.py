import asyncio
import logging
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.database.models import ModelConfig
from app.supervisors.vram_arbiter import vram_arbiter

logger = logging.getLogger(__name__)


class ModelState(StrEnum):
    UNLOADED = "Unloaded"
    LOADING = "Loading"
    READY = "Ready"
    IN_USE = "In Use"
    UNLOADING = "Unloading"
    FAILED = "Failed"


class ModelSupervisor:
    def __init__(self):
        self.state: ModelState = ModelState.UNLOADED
        self.active_model: ModelConfig | None = None
        self.process: subprocess.Popen | None = None
        self.last_active_at: datetime | None = None
        self.active_requests: int = 0
        self.lock = asyncio.Lock()
        self.slot_semaphore = asyncio.Semaphore(settings.LLAMA_PARALLEL_SLOTS)

    @property
    def base_url(self) -> str:
        return f"http://{settings.LLAMA_SERVER_HOST}:{settings.LLAMA_SERVER_PORT}"

    def get_status(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "active_model_id": self.active_model.id if self.active_model else None,
            "active_model_name": self.active_model.display_name if self.active_model else None,
            "active_requests": self.active_requests,
            "available_slots": self.slot_semaphore._value,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "vram": vram_arbiter.get_vram_status(),
        }

    async def load_model(self, model: ModelConfig) -> None:
        async with self.lock:
            if self.active_model and self.active_model.id == model.id:
                if self.state == ModelState.READY:
                    logger.info(f"Model '{model.display_name}' is already loaded and ready.")
                    return

            if self.active_requests > 0:
                raise RuntimeError("Cannot switch models while inference requests are active")

            # Terminate any previously running model process first
            if self.process:
                await self._stop_process()

            model_path = Path(model.file_path)
            if not model_path.exists():
                self.state = ModelState.FAILED
                raise FileNotFoundError(f"Model file not found at: {model.file_path}")

            # Verify and auto-tune GPU layers to stay within the 80% ceiling
            if model.gpu_layers == -1:
                calculated_layers = vram_arbiter.calculate_optimal_gpu_layers(
                    file_size_bytes=model_path.stat().st_size,
                    context_length=model.context_length,
                    total_model_layers=28,
                )
                logger.info(
                    f"Auto-tuning GPU layers: offloading {calculated_layers}/28 layers to GPU "
                    f"to respect the {settings.MAX_GPU_USAGE_PERCENT}% VRAM ceiling."
                )
            else:
                calculated_layers = model.gpu_layers

            self.state = ModelState.LOADING
            self.active_model = model

            # Build llama-server launch command
            cmd = [
                settings.LLAMA_SERVER_BIN,
                "-m",
                str(model_path),
                "-c",
                str(model.context_length),
                "-ngl",
                str(calculated_layers),
                "--host",
                settings.LLAMA_SERVER_HOST,
                "--port",
                str(settings.LLAMA_SERVER_PORT),
                "--parallel",
                str(settings.LLAMA_PARALLEL_SLOTS),
            ]

            # Multimodal projector flag for vision-language models
            if model.vision_supported and model.mmproj_path:
                mmproj_file = Path(model.mmproj_path)
                if not mmproj_file.exists():
                    self.state = ModelState.FAILED
                    raise FileNotFoundError(f"mmproj file not found at: {model.mmproj_path}")
                cmd.extend(["--mmproj", str(mmproj_file)])

            try:
                logger.info(f"Spawning llama-server process: {' '.join(cmd)}")
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                # Wait for health endpoint readiness
                await self._wait_for_ready(timeout_seconds=90)
                self.state = ModelState.READY
                self.last_active_at = datetime.now(UTC)
                logger.info(f"Model '{model.display_name}' is loaded and ready for inference.")
            except Exception as e:
                self.state = ModelState.FAILED
                await self._stop_process()
                logger.error(f"Failed to start llama-server: {e}", exc_info=True)
                raise

    async def _wait_for_ready(self, timeout_seconds: int = 90) -> None:
        async with httpx.AsyncClient() as client:
            for _ in range(timeout_seconds):
                if self.process and self.process.poll() is not None:
                    stderr = self.process.stderr.read() if self.process.stderr else ""
                    raise RuntimeError(f"llama-server terminated unexpectedly: {stderr}")
                try:
                    res = await client.get(f"{self.base_url}/health", timeout=1.0)
                    if res.status_code == 200:
                        return
                except httpx.RequestError:
                    pass
                await asyncio.sleep(1)
        raise TimeoutError("Timed out waiting for llama-server to become healthy.")

    async def unload_model(self) -> None:
        async with self.lock:
            if self.active_requests > 0:
                raise RuntimeError("Cannot unload model with active requests in progress")
            await self._stop_process()
            self.state = ModelState.UNLOADED
            self.active_model = None
            logger.info("Model successfully unloaded.")

    async def _stop_process(self) -> None:
        self.state = ModelState.UNLOADING
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            finally:
                self.process = None


model_supervisor = ModelSupervisor()
