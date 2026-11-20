import json
import logging
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class HardwareProbe:
    def __init__(self):
        self.system = platform.system()
        self.machine = platform.machine()

    def _detect_cpu_features(self) -> list[str]:
        """Detects CPU SIMD instruction sets (AVX-512, AVX2, NEON)."""
        features: list[str] = []
        if self.machine in ("arm64", "aarch64"):
            features.append("NEON")
            return features

        try:
            if self.system == "Linux" and Path("/proc/cpuinfo").exists():
                cpuinfo = Path("/proc/cpuinfo").read_text().lower()
                if "avx512" in cpuinfo:
                    features.append("AVX-512")
                if "avx2" in cpuinfo:
                    features.append("AVX2")
                elif "avx" in cpuinfo:
                    features.append("AVX")
            elif self.system == "Darwin":
                out = (
                    subprocess.check_output(["sysctl", "-a"])
                    .decode("utf-8", errors="ignore")
                    .lower()
                )
                if "avx512" in out:
                    features.append("AVX-512")
                if "avx2" in out:
                    features.append("AVX2")
        except Exception:
            pass

        return features or ["Standard"]

    def _get_system_ram_mb(self) -> int:
        try:
            if self.system == "Darwin":
                ram_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
                return int(ram_bytes / (1024 * 1024))
            elif self.system == "Linux" and Path("/proc/meminfo").exists():
                meminfo = Path("/proc/meminfo").read_text()
                m = re.search(r"MemTotal:\s+(\d+)\s+kB", meminfo)
                if m:
                    return int(int(m.group(1)) / 1024)
        except Exception:
            pass
        return 8192

    def _get_amd_rocm_info(self) -> dict[str, Any] | None:
        """Queries AMD ROCm GPU VRAM via rocm-smi or Linux DRM sysfs."""
        if not (os.path.exists("/dev/kfd") or shutil.which("rocm-smi")):
            return None

        total_mb = 8192
        used_mb = 0
        device_name = "AMD Radeon GPU (ROCm)"

        # Try Linux sysfs VRAM counters first (fast, zero-dependency)
        for card_dir in Path("/sys/class/drm").glob("card*/device"):
            total_file = card_dir / "mem_info_vram_total"
            used_file = card_dir / "mem_info_vram_used"
            if total_file.exists():
                try:
                    total_mb = int(int(total_file.read_text().strip()) / (1024 * 1024))
                    if used_file.exists():
                        used_mb = int(int(used_file.read_text().strip()) / (1024 * 1024))
                    break
                except Exception:
                    pass

        # Refine via rocm-smi if available
        if shutil.which("rocm-smi"):
            try:
                out = subprocess.check_output(
                    ["rocm-smi", "--showproductname", "--json"],
                    stderr=subprocess.DEVNULL,
                ).decode("utf-8")
                data = json.loads(out)
                first_card = next(iter(data.values()), {})
                if "Card series" in first_card:
                    device_name = first_card["Card series"]
            except Exception:
                pass

        return {
            "backend": "rocm",
            "device_name": device_name,
            "total_vram_mb": total_mb,
            "used_vram_mb": used_mb,
        }

    def detect_accelerator(self) -> dict[str, Any]:
        """Probes system hardware to determine optimal GGML backend and memory budget."""
        cpu_simd = self._detect_cpu_features()
        sys_ram_mb = self._get_system_ram_mb()

        profile: dict[str, Any] = {
            "system": self.system,
            "machine": self.machine,
            "backend": "cpu",
            "device_name": f"CPU ({', '.join(cpu_simd)})",
            "cpu_simd": cpu_simd,
            "system_ram_mb": sys_ram_mb,
            "total_vram_mb": sys_ram_mb,
            "used_vram_mb": 0,
        }

        env_override = settings.AIWA_HARDWARE_ACCELERATION.lower().strip()

        # 1. Apple Silicon (macOS Metal)
        if (
            env_override in ("auto", "metal")
            and self.system == "Darwin"
            and self.machine == "arm64"
        ):
            profile["backend"] = "metal"
            profile["device_name"] = "Apple Silicon (Metal Unified Memory)"
            profile["total_vram_mb"] = sys_ram_mb
            return profile

        # 2. NVIDIA CUDA
        if env_override in ("auto", "cuda") and (
            shutil.which("nvidia-smi") or os.path.exists("/proc/driver/nvidia")
        ):
            profile["backend"] = "cuda"
            profile["device_name"] = "NVIDIA GPU (CUDA)"
            try:
                import pynvml

                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                name = pynvml.nvmlDeviceGetName(handle)
                profile["device_name"] = (
                    name.decode("utf-8") if isinstance(name, bytes) else str(name)
                )
                profile["total_vram_mb"] = int(info.total / (1024 * 1024))
                profile["used_vram_mb"] = int(info.used / (1024 * 1024))
            except Exception:
                pass
            return profile

        # 3. AMD ROCm / HIP
        if env_override in ("auto", "rocm"):
            amd_info = self._get_amd_rocm_info()
            if amd_info:
                profile.update(amd_info)
                return profile

        # 4. Vulkan Compute (Cross-vendor Intel Arc / AMD / NVIDIA)
        if env_override in ("auto", "vulkan") and shutil.which("vulkaninfo"):
            profile["backend"] = "vulkan"
            profile["device_name"] = "Vulkan Compute GPU"
            return profile

        # 5. Forced or Fallback CPU SIMD
        profile["backend"] = "cpu"
        profile["device_name"] = f"CPU ({self.machine} • {', '.join(cpu_simd)})"
        return profile


hardware_probe = HardwareProbe()
