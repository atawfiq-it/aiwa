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
            logger.info("NVML initialized. Dynamic GPU allocation active.")
        except Exception as e:
            self._has_nvml = False
            logger.warning(
                f"NVML unavailable ({e}). Using static fallback budget: "
                f"{settings.DEFAULT_STATIC_VRAM_GB} GB"
            )

    def get_vram_status(self) -> dict[str, Any]:
        """Returns total, free, used, and allowed budget in MB."""
        if self._has_nvml:
            try:
                import pynvml

                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_mb = int(info.total / (1024 * 1024))
                used_mb = int(info.used / (1024 * 1024))
                free_mb = int(info.free / (1024 * 1024))
                allowed_ceiling_mb = int(total_mb * (settings.MAX_GPU_USAGE_PERCENT / 100.0))
                effective_free_mb = max(0, allowed_ceiling_mb - used_mb)

                return {
                    "provider": "nvidia_nvml",
                    "total_mb": total_mb,
                    "used_mb": used_mb,
                    "free_mb": free_mb,
                    "max_usage_percent": settings.MAX_GPU_USAGE_PERCENT,
                    "allowed_ceiling_mb": allowed_ceiling_mb,
                    "effective_free_mb": effective_free_mb,
                }
            except Exception as e:
                logger.error(f"Failed querying NVML: {e}")

        total_mb = int(settings.DEFAULT_STATIC_VRAM_GB * 1024)
        allowed_ceiling_mb = int(total_mb * (settings.MAX_GPU_USAGE_PERCENT / 100.0))
        return {
            "provider": "static_fallback",
            "total_mb": total_mb,
            "used_mb": 0,
            "free_mb": total_mb,
            "max_usage_percent": settings.MAX_GPU_USAGE_PERCENT,
            "allowed_ceiling_mb": allowed_ceiling_mb,
            "effective_free_mb": allowed_ceiling_mb,
        }

    def calculate_optimal_gpu_layers(
        self,
        file_size_bytes: int,
        context_length: int,
        total_model_layers: int = 36,
    ) -> int:
        """Calculates how many layers can fit strictly within the 80% VRAM budget."""
        status = self.get_vram_status()
        available_mb = status.get("effective_free_mb", 0)

        # Context length footprint and runtime overhead
        kv_cache_mb = int((max(512, context_length) / 1024) * 64)
        runtime_overhead_mb = 256
        usable_for_weights_mb = available_mb - (kv_cache_mb + runtime_overhead_mb)

        if usable_for_weights_mb <= 0:
            return 0  # Offload to CPU if GPU budget is filled

        total_weights_mb = int(file_size_bytes / (1024 * 1024))
        if total_weights_mb <= 0 or total_model_layers <= 0:
            return 0

        mb_per_layer = total_weights_mb / float(total_model_layers)
        if mb_per_layer <= 0:
            return 0

        fit_layers = int(usable_for_weights_mb / mb_per_layer)
        return max(0, min(total_model_layers, fit_layers))


vram_arbiter = VRAMArbiter()
