import asyncio
import logging
import os
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
                    return

            if self.active_requests > 0:
                raise RuntimeError("Cannot switch models while inference requests are active")

            # Unload any currently running instance first
            if self.process:
                await self._stop_process()

            model_path = Path(model.file_path).resolve()
            if not model_path.exists():
                self.state = ModelState.FAILED
                raise FileNotFoundError(f"Model file not found at: {model.file_path}")

            # Verify and resolve multimodal projector for vision models
            mmproj_resolved: Path | None = None
            if model.vision_supported and model.mmproj_path:
                mmproj_resolved = Path(model.mmproj_path).resolve()
                if not mmproj_resolved.exists():
                    self.state = ModelState.FAILED
                    raise FileNotFoundError(
                        f"Multimodal projector file not found at: {model.mmproj_path}"
                    )

            # Auto-tune layers to fit inside the configured GPU budget (e.g. 80% ceiling)
            if model.gpu_layers == -1:
                calculated_layers = vram_arbiter.calculate_optimal_gpu_layers(
                    file_size_bytes=model_path.stat().st_size,
                    context_length=model.context_length,
                    total_model_layers=36,
                )
                logger.info(
                    f"Auto-tuned GPU layers: offloading {calculated_layers}/36 layers to GPU "
                    f"to respect {settings.MAX_GPU_USAGE_PERCENT}% ceiling."
                )
            else:
                calculated_layers = model.gpu_layers

            self.state = ModelState.LOADING
            self.active_model = model

            server_bin = Path(settings.LLAMA_SERVER_BIN).resolve()
            cmd = [
                str(server_bin),
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

            # Fix for custom/experimental architecture tags (qwen3 -> qwen2)
            # if "qwen3" in model_path.name.lower() or "qwen3" in str(model_path).lower():
            #     logger.info("Applying metadata override: general.architecture=str:qwen2")
            #     cmd.extend(["--override-kv", "general.architecture=str:qwen2"])

            if model.vision_supported and model.mmproj_path:
                cmd.extend(["--mmproj", str(model.mmproj_path)])

            if mmproj_resolved:
                cmd.extend(["--mmproj", str(mmproj_resolved)])

            # Inject LD_LIBRARY_PATH so dynamic linker locates libllama.so
            server_dir = str(server_bin.parent)
            proc_env = os.environ.copy()
            current_ld = proc_env.get("LD_LIBRARY_PATH", "")
            proc_env["LD_LIBRARY_PATH"] = f"{server_dir}:{current_ld}" if current_ld else server_dir

            try:
                logger.info(f"Spawning llama-server: {' '.join(cmd)}")
                # Do not hide stdout/stderr in a blind pipe; inherit or log so progress is visible
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=None,  # Prints llama.cpp load progress directly to daemon terminal
                )

                # Wait for server /health readiness (increased to 120s)
                await self._wait_for_ready(timeout_seconds=120)
                self.state = ModelState.READY
                self.last_active_at = datetime.now(UTC)
                logger.info(f"Model {model.display_name} loaded and ready.")
            except Exception as e:
                self.state = ModelState.FAILED
                await self._stop_process()
                logger.error(f"Failed to start llama-server: {e}")
                raise

    async def _wait_for_ready(self, timeout_seconds: int = 120) -> None:
        async with httpx.AsyncClient() as client:
            for _ in range(timeout_seconds):
                if self.process and self.process.poll() is not None:
                    raise RuntimeError("llama-server terminated unexpectedly.")
                try:
                    res = await client.get(f"{self.base_url}/health", timeout=1.0)
                    if res.status_code == 200:
                        return
                except httpx.RequestError:
                    pass
                await asyncio.sleep(1)
        raise TimeoutError(
            f"Timed out after {timeout_seconds}s waiting for llama-server readiness."
        )

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
