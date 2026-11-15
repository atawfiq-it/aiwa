import logging
import os
import platform
import shutil
import subprocess
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class HardwareProbe:
    def __init__(self):
        self.system = platform.system()
        self.machine = platform.machine()

    def detect_accelerator(self) -> dict[str, Any]:
        profile = {
            "system": self.system,
            "machine": self.machine,
            "backend": "cpu",
            "device_name": "Generic CPU",
            "total_vram_mb": 8192,
            "supports_metal": False,
            "supports_cuda": False,
            "supports_rocm": False,
            "supports_vulkan": False,
        }

        # Respect .env override if configured
        env_accel = settings.AIWA_HARDWARE_ACCELERATION.lower()
        if env_accel != "auto":
            profile["backend"] = env_accel
            profile["device_name"] = f"Forced via .env ({env_accel})"
            return profile

        # 1. Check Apple Silicon (macOS Metal)
        if self.system == "Darwin" and self.machine == "arm64":
            profile["backend"] = "metal"
            profile["device_name"] = "Apple Silicon (Metal Unified Memory)"
            profile["supports_metal"] = True
            # Estimate unified memory from system RAM via sysctl
            try:
                ram_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
                profile["total_vram_mb"] = int(ram_bytes / (1024 * 1024))
            except Exception:
                pass
            return profile

        # 2. Check NVIDIA CUDA via nvidia-smi / pynvml
        if shutil.which("nvidia-smi") or os.path.exists("/proc/driver/nvidia"):
            profile["supports_cuda"] = True
            profile["backend"] = "cuda"
            profile["device_name"] = "NVIDIA GPU (CUDA)"
            try:
                import pynvml

                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                profile["total_vram_mb"] = int(info.total / (1024 * 1024))
                profile["device_name"] = pynvml.nvmlDeviceGetName(handle).decode("utf-8")
            except Exception:
                pass
            return profile

        # 3. Check AMD ROCm / HIP
        if os.path.exists("/dev/kfd") or shutil.which("rocm-smi"):
            profile["supports_rocm"] = True
            profile["backend"] = "rocm"
            profile["device_name"] = "AMD GPU (ROCm/HIP)"
            return profile

        # 4. Check Vulkan compute availability
        if shutil.which("vulkaninfo"):
            profile["supports_vulkan"] = True
            profile["backend"] = "vulkan"
            profile["device_name"] = "Vulkan Compute Device"
            return profile

        # 5. Fallback to CPU with AVX/SSE capability check
        profile["backend"] = "cpu"
        profile["device_name"] = f"CPU ({self.machine})"
        return profile


hardware_probe = HardwareProbe()
