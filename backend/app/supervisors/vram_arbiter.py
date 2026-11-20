import logging
import platform
import re
import subprocess
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class VRAMArbiter:
    def __init__(self):
        self._has_nvml = False
        self._init_nvml()

    def _init_nvml(self) -> None:
        if platform.system() == "Darwin":
            self._has_nvml = False
            logger.info("🍎 Apple Silicon detected. Using macOS Unified Memory Arbiter.")
            return

        try:
            import pynvml

            pynvml.nvmlInit()
            self._has_nvml = True
            logger.info("NVML initialized. Dynamic GPU allocation active.")
        except Exception as e:
            self._has_nvml = False
            logger.warning(
                f"NVML unavailable ({e}). Using hardware probe / static budget: "
                f"{settings.DEFAULT_STATIC_VRAM_GB} GB"
            )

    def _get_apple_metal_memory(self) -> dict[str, Any] | None:
        """Queries macOS Apple Silicon Unified Memory via sysctl and vm_stat."""
        if platform.system() != "Darwin":
            return None
        try:
            total_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
            total_mb = int(total_bytes / (1024 * 1024))

            vm_out = subprocess.check_output(["vm_stat"]).decode("utf-8")
            page_size_match = re.search(r"page size of (\d+) bytes", vm_out)
            page_size = int(page_size_match.group(1)) if page_size_match else 16384

            def extract_pages(label: str) -> int:
                m = re.search(rf"{label}:\s+(\d+)\.", vm_out)
                return int(m.group(1)) if m else 0

            free_pages = extract_pages("Pages free") + extract_pages("Pages inactive")
            free_mb = int((free_pages * page_size) / (1024 * 1024))
            used_mb = max(0, total_mb - free_mb)

            allowed_ceiling_mb = int(total_mb * (settings.MAX_GPU_USAGE_PERCENT / 100.0))
            effective_free_mb = max(0, allowed_ceiling_mb - used_mb)

            return {
                "provider": "apple_metal_unified",
                "device_name": "Apple Silicon (Metal Unified Memory)",
                "total_mb": total_mb,
                "used_mb": used_mb,
                "free_mb": free_mb,
                "max_usage_percent": settings.MAX_GPU_USAGE_PERCENT,
                "allowed_ceiling_mb": allowed_ceiling_mb,
                "effective_free_mb": effective_free_mb,
            }
        except Exception as e:
            logger.warning(f"Failed reading macOS unified memory: {e}")
            return None

    def get_vram_status(self) -> dict[str, Any]:
        """Returns unified memory status across Apple Metal, CUDA, AMD ROCm, Vulkan, or CPU RAM."""
        # 1. Apple Silicon Metal Unified Memory
        apple_mem = self._get_apple_metal_memory()
        if apple_mem:
            return apple_mem

        # 2. Hardware Probe (CUDA, ROCm, Vulkan, CPU)
        from app.supervisors.hardware_probe import hardware_probe

        hw = hardware_probe.detect_accelerator()
        total_mb = hw["total_vram_mb"]
        used_mb = hw["used_vram_mb"]
        free_mb = max(0, total_mb - used_mb)
        allowed_ceiling_mb = int(total_mb * (settings.MAX_GPU_USAGE_PERCENT / 100.0))
        effective_free_mb = max(0, allowed_ceiling_mb - used_mb)

        return {
            "provider": hw["backend"],
            "device_name": hw["device_name"],
            "total_mb": total_mb,
            "used_mb": used_mb,
            "free_mb": free_mb,
            "max_usage_percent": settings.MAX_GPU_USAGE_PERCENT,
            "allowed_ceiling_mb": allowed_ceiling_mb,
            "effective_free_mb": effective_free_mb,
        }

    def estimate_vram_required_mb(self, file_size_bytes: int, context_length: int) -> int:
        """Estimate VRAM required for model weights + KV cache."""
        weights_mb = int(file_size_bytes / (1024 * 1024))
        kv_cache_mb = int((context_length / 1024) * 64)
        runtime_overhead_mb = 256
        return weights_mb + kv_cache_mb + runtime_overhead_mb

    def can_fit_model(self, estimated_mb: int) -> bool:
        """Validates if model fits within the configured VRAM ceiling."""
        status = self.get_vram_status()
        return estimated_mb <= status["effective_free_mb"]

    def calculate_optimal_gpu_layers(
        self,
        file_size_bytes: int,
        context_length: int,
        total_model_layers: int = 28,
    ) -> int:
        """Calculates how many layers can fit strictly within the configured VRAM budget."""
        status = self.get_vram_status()
        available_mb = status["effective_free_mb"]

        kv_cache_mb = int((context_length / 1024) * 64)
        runtime_overhead_mb = 256
        usable_for_weights_mb = available_mb - (kv_cache_mb + runtime_overhead_mb)

        if usable_for_weights_mb <= 0:
            return 0

        total_weights_mb = max(1, int(file_size_bytes / (1024 * 1024)))
        mb_per_layer = total_weights_mb / total_model_layers

        fit_layers = int(usable_for_weights_mb / mb_per_layer)
        return max(0, min(total_model_layers, fit_layers))


vram_arbiter = VRAMArbiter()
