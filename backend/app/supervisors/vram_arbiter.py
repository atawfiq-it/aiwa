import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class VRAMArbiter:
    def __init__(self):
        self._has_nvml = False
        self._init_nvml()

    def _init_nvml(self) -> None:
        try:
            import pynvml

            pynvml.nvmlInit()
            self._has_nvml = True
            logger.info("NVML initialized successfully. Hardware GPU monitoring enabled.")
        except Exception as e:
            self._has_nvml = False
            logger.warning(
                f"NVML unavailable ({e}). Using static VRAM budget: "
                f"{settings.DEFAULT_STATIC_VRAM_GB} GB"
            )

    def get_vram_status(self) -> dict[str, Any]:
        """Returns total, free, and used VRAM in megabytes."""
        if self._has_nvml:
            try:
                import pynvml

                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                return {
                    "provider": "nvidia_nvml",
                    "total_mb": int(info.total / (1024 * 1024)),
                    "free_mb": int(info.free / (1024 * 1024)),
                    "used_mb": int(info.used / (1024 * 1024)),
                }
            except Exception as e:
                logger.error(f"Failed querying NVML: {e}")

        # Fallback to configured static budget
        total_mb = int(settings.DEFAULT_STATIC_VRAM_GB * 1024)
        return {
            "provider": "static_fallback",
            "total_mb": total_mb,
            "free_mb": total_mb,
            "used_mb": 0,
        }

    def estimate_vram_required_mb(self, file_size_bytes: int, context_length: int) -> int:
        """Estimate VRAM required for model weights + KV cache."""
        weights_mb = int(file_size_bytes / (1024 * 1024))
        # Approximation: ~1MB KV cache per 1k tokens for typical 7B-14B models
        kv_cache_mb = int((context_length / 1024) * 64)
        runtime_overhead_mb = 256
        return weights_mb + kv_cache_mb + runtime_overhead_mb

    def can_fit_model(self, estimated_mb: int) -> bool:
        status = self.get_vram_status()
        available_mb = status["free_mb"] - settings.VRAM_SAFETY_MARGIN_MB
        return estimated_mb <= available_mb


vram_arbiter = VRAMArbiter()
