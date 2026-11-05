import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModelScannerService:
    @staticmethod
    def _detect_quantization(filename: str) -> str | None:
        match = re.search(r"(Q[0-9]_[A-Z0-9_]+|f16|f32|bf16)", filename, re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _is_vision_model(filename: str) -> bool:
        lower = filename.lower()
        return any(
            k in lower for k in ["-vl", "vision", "llava", "qwen-vl", "qwen2-vl", "qwen2.5-vl"]
        )

    def scan_directories(self, search_paths: list[str]) -> list[dict[str, Any]]:
        """Deep recursive scan across all sub-directory levels for LLM, Diffusion, and Voice models."""
        discovered_models: list[dict[str, Any]] = []
        mmproj_files: dict[str, Path] = {}

        valid_dirs: list[Path] = []
        for p in search_paths:
            path_obj = Path(p).resolve()
            if path_obj.exists() and path_obj.is_dir():
                valid_dirs.append(path_obj)
            else:
                logger.warning(f"Scan path does not exist: {p}")

        # Pass 1: Recursive indexing of multimodal projectors across all depths
        for root_dir in valid_dirs:
            for root, _, files in os.walk(root_dir, followlinks=True):
                for f in files:
                    if f.lower().endswith(".gguf") and "mmproj" in f.lower():
                        proj_path = Path(root) / f
                        mmproj_files[proj_path.stem] = proj_path

        # Pass 2: Recursive indexing of all models across all subdirectories
        for root_dir in valid_dirs:
            for root, _, files in os.walk(root_dir, followlinks=True):
                for f in files:
                    file_path = Path(root) / f
                    fname_lower = f.lower()

                    # A. LLM & Vision Models (.gguf)
                    if fname_lower.endswith(".gguf"):
                        if "mmproj" in fname_lower:
                            continue  # Projector already cataloged

                        size_bytes = file_path.stat().st_size
                        is_vision = self._is_vision_model(f)
                        matched_mmproj = None
                        if is_vision:
                            for proj_name, proj_p in mmproj_files.items():
                                if "qwen" in fname_lower and "qwen" in proj_name.lower():
                                    matched_mmproj = str(proj_p)
                                    break
                                elif proj_p.parent == file_path.parent:
                                    matched_mmproj = str(proj_p)
                                    break

                        discovered_models.append(
                            {
                                "category": "llm",
                                "display_name": file_path.stem.replace("-Q4_K_M", "").replace(
                                    "_", " "
                                ),
                                "file_path": str(file_path),
                                "file_size_gb": round(size_bytes / (1024**3), 2),
                                "file_size_bytes": size_bytes,
                                "quantization": self._detect_quantization(f),
                                "vision_supported": is_vision and matched_mmproj is not None,
                                "mmproj_path": matched_mmproj,
                                "directory": str(root),
                            }
                        )

                    # B. Diffusion / Image Generation Models (.safetensors, .ckpt)
                    elif fname_lower.endswith((".safetensors", ".ckpt")):
                        size_bytes = file_path.stat().st_size
                        if size_bytes > 500 * 1024 * 1024:  # Filter out tiny adapter files (<500MB)
                            discovered_models.append(
                                {
                                    "category": "diffusion",
                                    "display_name": file_path.stem.replace("_", " "),
                                    "file_path": str(file_path),
                                    "file_size_gb": round(size_bytes / (1024**3), 2),
                                    "file_size_bytes": size_bytes,
                                    "quantization": "fp16" if "fp16" in fname_lower else "fp32",
                                    "vision_supported": False,
                                    "mmproj_path": None,
                                    "directory": str(root),
                                }
                            )

                    # C. Voice / Speech Models (.onnx, Whisper / Kokoro weights)
                    elif fname_lower.endswith((".onnx", ".bin")) and any(
                        k in fname_lower for k in ["whisper", "kokoro", "tts", "stt", "voice"]
                    ):
                        size_bytes = file_path.stat().st_size
                        discovered_models.append(
                            {
                                "category": "voice",
                                "display_name": file_path.stem.replace("_", " "),
                                "file_path": str(file_path),
                                "file_size_gb": round(size_bytes / (1024**3), 2),
                                "file_size_bytes": size_bytes,
                                "quantization": "int8" if "int8" in fname_lower else "fp32",
                                "vision_supported": False,
                                "mmproj_path": None,
                                "directory": str(root),
                            }
                        )

        return discovered_models


model_scanner = ModelScannerService()
