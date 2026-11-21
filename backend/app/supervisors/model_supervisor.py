import asyncio
import logging
import platform
import subprocess
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.database.models import ModelConfig
from app.supervisors.vram_arbiter import vram_arbiter
from app.utils.port_manager import resolve_port_conflict

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

    async def flush_external_gpu_caches(self) -> None:
        """Stops any lingering ComfyUI service and flushes PyTorch CUDA/MPS memory caches."""
        import gc

        try:
            from app.supervisors.comfyui_supervisor import comfyui_supervisor

            await comfyui_supervisor.stop()
        except Exception:
            pass

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
        except Exception:
            pass

    async def ensure_loaded_on_demand(self, model_id: str | None = None) -> ModelConfig:
        """Ensures the requested or default LLM is loaded, unloading external GPU consumers first."""
        if self.state == ModelState.READY and self.active_model:
            if not model_id or self.active_model.id == model_id:
                return self.active_model

        # 1. Clear diffusion/external caches before loading LLM
        await self.flush_external_gpu_caches()

        # 2. Resolve target model from ID, last active, or DB default
        from sqlmodel import Session, select

        from app.database.engine import engine

        with Session(engine) as db:
            target = None
            if model_id:
                target = db.get(ModelConfig, model_id)
            if not target and self.active_model:
                target = db.get(ModelConfig, self.active_model.id)
            if not target:
                target = db.exec(
                    select(ModelConfig).where(ModelConfig.is_default == True)  # noqa: E712
                ).first()
            if not target:
                target = db.exec(select(ModelConfig)).first()

            if not target:
                raise RuntimeError("No LLM models are registered in the database.")

        logger.info(f"⚡ On-Demand Load: Waking up '{target.display_name}'...")
        await self.load_model(target)
        return target

    def is_idle_for(self, seconds: float) -> bool:
        """Returns True if zero inference requests are active and idle duration exceeds threshold."""
        if self.active_requests > 0:
            return False
        if not self.last_active_at:
            return True
        elapsed = (datetime.now(UTC) - self.last_active_at).total_seconds()
        return elapsed >= seconds

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

            if self.process:
                await self._stop_process()

            model_path = Path(model.file_path)
            if not model_path.exists():
                self.state = ModelState.FAILED
                raise FileNotFoundError(f"Model path not found at: {model.file_path}")

            self.state = ModelState.LOADING
            self.active_model = model

            # 1. Detect MLX Directory vs GGUF File
            is_mlx = model.format == "mlx" or (
                model_path.is_dir() and (model_path / "config.json").exists()
            )
            is_vision = model.vision_supported or (
                model_path.is_dir() and (model_path / "preprocessor_config.json").exists()
            )

            if is_mlx:
                if platform.system() != "Darwin":
                    raise RuntimeError("MLX models are only supported on macOS Apple Silicon.")

                worker_script = (
                    Path(__file__).resolve().parent.parent / "services" / "models" / "mlx_worker.py"
                )

                # Auto-reclaim orphaned engine or surface conflict to UI
                resolved_port = resolve_port_conflict(
                    host=settings.LLAMA_SERVER_HOST,
                    port=settings.LLAMA_SERVER_PORT,
                    service_name="LLM Inference Engine",
                    interactive_cli=False,
                )
                settings.LLAMA_SERVER_PORT = resolved_port

                cmd = [
                    sys.executable,
                    str(worker_script),
                    "--model",
                    str(model_path),
                    "--host",
                    settings.LLAMA_SERVER_HOST,
                    "--port",
                    str(settings.LLAMA_SERVER_PORT),
                ]
                if is_vision:
                    cmd.append("--vision")
                logger.info(f"🍎 Spawning Apple MLX Worker (Vision={is_vision}): {' '.join(cmd)}")
            else:
                if model_path.is_dir():
                    self.state = ModelState.FAILED
                    raise RuntimeError(f"Cannot load directory '{model_path}' with llama-server.")

                calculated_layers = (
                    vram_arbiter.calculate_optimal_gpu_layers(
                        file_size_bytes=model_path.stat().st_size,
                        context_length=model.context_length,
                        total_model_layers=28,
                    )
                    if model.gpu_layers == -1
                    else model.gpu_layers
                )
                effective_ctx_per_slot = max(model.context_length, 4096)
                total_server_context = effective_ctx_per_slot * settings.LLAMA_PARALLEL_SLOTS

                cmd = [
                    settings.LLAMA_SERVER_BIN,
                    "-m",
                    str(model_path),
                    "-c",
                    str(total_server_context),
                    "-ngl",
                    str(calculated_layers),
                    "--host",
                    settings.LLAMA_SERVER_HOST,
                    "--port",
                    str(settings.LLAMA_SERVER_PORT),
                    "--parallel",
                    str(settings.LLAMA_PARALLEL_SLOTS),
                    "--media-path",
                    str(settings.UPLOADS_DIR.resolve()),
                ]

                if is_vision and model.mmproj_path:
                    cmd.extend(["--mmproj", str(model.mmproj_path)])

                logger.info(f"Spawning llama-server: {' '.join(cmd)}")

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=None,
                    stderr=None,
                )

                await self._wait_for_ready(timeout_seconds=120)
                self.state = ModelState.READY
                self.last_active_at = datetime.now(UTC)
                logger.info(f"Model {model.display_name} loaded and ready.")
            except Exception as e:
                self.state = ModelState.FAILED
                await self._stop_process()
                logger.error(f"Failed to start inference engine: {e}")
                raise

    async def _wait_for_ready(self, timeout_seconds: int = 120) -> None:
        async with httpx.AsyncClient() as client:
            for _ in range(timeout_seconds):
                if self.process and self.process.poll() is not None:
                    raise RuntimeError("Inference engine terminated unexpectedly.")
                try:
                    res = await client.get(f"{self.base_url}/health", timeout=1.0)
                    if res.status_code == 200:
                        return
                except httpx.RequestError:
                    pass
                await asyncio.sleep(1)
        raise TimeoutError(f"Timed out after {timeout_seconds}s waiting for inference server.")

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
