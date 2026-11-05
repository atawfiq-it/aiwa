import asyncio
import logging
import subprocess

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ComfyUISupervisor:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.base_dir = settings.BASE_DIR / "services" / "comfyui"
        self.python_bin = self.base_dir / ".venv" / "bin" / "python"
        self.app_dir = self.base_dir / "app"

    def is_installed(self) -> bool:
        return self.python_bin.exists() and (self.app_dir / "main.py").exists()

    async def ensure_running(self) -> None:
        """Starts ComfyUI if not already running."""
        from app.services.media.comfyui import comfyui_adapter

        if await comfyui_adapter.is_available():
            return

        if not self.is_installed():
            raise FileNotFoundError("ComfyUI is not installed. Run 'just install-comfyui' first.")

        cmd = [
            str(self.python_bin),
            "main.py",
            "--port",
            "8188",
            "--listen",
            "127.0.0.1",
            "--preview-method",
            "none",
        ]

        logger.info("Spawning embedded ComfyUI process...")
        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.app_dir),
            stdout=subprocess.DEVNULL,
            stderr=None,
        )

        # Wait for readiness
        async with httpx.AsyncClient() as client:
            for _ in range(45):
                try:
                    res = await client.get(f"{settings.COMFYUI_BASE_URL}/system_stats", timeout=1.0)
                    if res.status_code == 200:
                        logger.info("✅ Embedded ComfyUI is Ready.")
                        return
                except httpx.RequestError:
                    pass
                await asyncio.sleep(1)

        raise TimeoutError("Timed out waiting for ComfyUI to start.")

    async def stop(self) -> None:
        if self.process:
            logger.info("Shutting down embedded ComfyUI...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            finally:
                self.process = None


comfyui_supervisor = ComfyUISupervisor()
