import asyncio
import logging
import subprocess
from datetime import datetime
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
                    return

            if self.active_requests > 0:
                raise RuntimeError("Cannot switch models while inference requests are active")

            # Unload any active model first
            if self.process:
                await self._stop_process()

            model_path = Path(model.file_path)
            if not model_path.exists():
                self.state = ModelState.FAILED
                raise FileNotFoundError(f"Model file not found at: {model.file_path}")

            # Verify VRAM limits
            est_mb = vram_arbiter.estimate_vram_required_mb(
                model_path.stat().st_size, model.context_length
            )
            if not vram_arbiter.can_fit_model(est_mb):
                self.state = ModelState.FAILED
                raise MemoryError(f"Insufficient VRAM: requires {est_mb}MB with safety margin.")

            self.state = ModelState.LOADING
            self.active_model = model

            cmd = [
                settings.LLAMA_SERVER_BIN,
                "-m",
                str(model_path),
                "-c",
                str(model.context_length),
                "-ngl",
                str(model.gpu_layers),
                "--host",
                settings.LLAMA_SERVER_HOST,
                "--port",
                str(settings.LLAMA_SERVER_PORT),
                "--parallel",
                str(settings.LLAMA_PARALLEL_SLOTS),
            ]

            if model.vision_supported and model.mmproj_path:
                cmd.extend(["--mmproj", str(model.mmproj_path)])

            try:
                logger.info(f"Spawning llama-server: {' '.join(cmd)}")
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                # Wait for server /health readiness
                await self._wait_for_ready(timeout_seconds=60)
                self.state = ModelState.READY
                self.last_active_at = datetime.utcnow()
                logger.info(f"Model {model.display_name} loaded and ready.")
            except Exception as e:
                self.state = ModelState.FAILED
                await self._stop_process()
                logger.error(f"Failed to start llama-server: {e}")
                raise

    async def _wait_for_ready(self, timeout_seconds: int = 60) -> None:
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
                raise RuntimeError("Cannot unload model with active requests")
            await self._stop_process()
            self.state = ModelState.UNLOADED
            self.active_model = None

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
