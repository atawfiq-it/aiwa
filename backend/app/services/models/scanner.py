import logging
import os
import re
from pathlib import Path
from typing import Any

from app.utils.safetensors_inspector import inspect_safetensors_type

logger = logging.getLogger(__name__)


class ModelScannerService:
    @staticmethod
    def _detect_quantization(filename: str) -> str | None:
        match = re.search(r"(Q[0-9]_[A-Z0-9_]+|f16|f32|bf16)", filename, re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _is_vision_model(filename: str) -> bool:
        lower = filename.lower()
        vision_keys = ["-vl", "vision", "llava", "qwen-vl", "qwen2-vl", "qwen2.5-vl"]
        return any(k in lower for k in vision_keys)

    def scan_directories(self, search_paths: list[str]) -> list[dict[str, Any]]:
        """Deep recursive scan across all subdirectories for GGUF, MLX, Diffusion, and Voice models."""
        discovered_models: list[dict[str, Any]] = []
        mmproj_files: dict[str, Path] = {}
        seen_paths: set[str] = set()

        valid_dirs: list[Path] = []
        for p in search_paths:
            path_obj = Path(p).resolve()
            if path_obj.exists() and path_obj.is_dir():
                valid_dirs.append(path_obj)
            else:
                logger.warning(f"Scan path does not exist or is not a directory: {p}")

        # Pass 1: Recursive indexing of multimodal projectors across all depths
        for root_dir in valid_dirs:
            for root, _, files in os.walk(root_dir, followlinks=True):
                for f in files:
                    file_path = Path(root) / f
                    if (
                        file_path.is_file()
                        and f.lower().endswith(".gguf")
                        and "mmproj" in f.lower()
                    ):
                        mmproj_files[file_path.stem] = file_path

        # Pass 2: Recursive indexing of GGUF, MLX, Diffusion, and Voice models
        for root_dir in valid_dirs:
            for root, _, files in os.walk(root_dir, followlinks=True):
                root_path = Path(root)

                # 1. Detect Apple MLX / Safetensors LLM directory bundle
                has_config = "config.json" in files
                has_tokenizer = "tokenizer.json" in files or "tokenizer_config.json" in files
                safetensor_files = [f for f in files if f.lower().endswith(".safetensors")]

                if has_config and has_tokenizer and safetensor_files:
                    first_shard = root_path / safetensor_files[0]
                    if first_shard.is_file() and inspect_safetensors_type(first_shard) == "llm":
                        total_bytes = sum(
                            (root_path / s).stat().st_size
                            for s in safetensor_files
                            if (root_path / s).is_file()
                        )
                        if total_bytes > 50 * 1024 * 1024:
                            # Detect vision support via preprocessor_config.json or folder name
                            is_vision = (
                                "preprocessor_config.json" in files
                                or "video_preprocessor_config.json" in files
                                or any(k in root_path.name.lower() for k in ["vl", "vision"])
                            )
                            discovered_models.append(
                                {
                                    "category": "llm",
                                    "format": "mlx",
                                    "display_name": f"{root_path.name}",
                                    "file_path": str(root_path.resolve()),
                                    "file_size_gb": round(total_bytes / (1024**3), 2),
                                    "file_size_bytes": total_bytes,
                                    "quantization": "MLX-4bit"
                                    if "4bit" in root_path.name.lower()
                                    else "MLX",
                                    "vision_supported": is_vision,
                                    "mmproj_path": None,
                                    "directory": str(root_path.parent),
                                }
                            )

                # 2. Scan individual files inside the current directory
                for f in files:
                    file_path = root_path / f
                    fname_lower = f.lower()

                    if not file_path.is_file() or file_path.is_dir():
                        continue

                    resolved_str = str(file_path.resolve())
                    if resolved_str in seen_paths:
                        continue

                    # A. LLM & Vision Models (.gguf)
                    if fname_lower.endswith(".gguf"):
                        if "mmproj" in fname_lower:
                            continue

                        size_bytes = file_path.stat().st_size
                        if size_bytes < 50 * 1024 * 1024:
                            continue

                        seen_paths.add(resolved_str)
                        is_vision = self._is_vision_model(f)
                        matched_mmproj = None
                        if is_vision:
                            for proj_name, proj_p in mmproj_files.items():
                                if "qwen" in fname_lower and "qwen" in proj_name.lower():
                                    matched_mmproj = str(proj_p.resolve())
                                    break
                                if proj_p.parent == file_path.parent:
                                    matched_mmproj = str(proj_p.resolve())
                                    break

                        clean_name = (
                            file_path.stem.replace("-Q4_K_M", "")
                            .replace(".Q4_K_M", "")
                            .replace("_", " ")
                        )
                        discovered_models.append(
                            {
                                "category": "llm",
                                "format": "gguf",
                                "display_name": clean_name,
                                "file_path": resolved_str,
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
                        if size_bytes < 500 * 1024 * 1024:
                            continue

                        if fname_lower.endswith(".safetensors"):
                            if inspect_safetensors_type(file_path) != "diffusion":
                                continue

                        seen_paths.add(resolved_str)
                        discovered_models.append(
                            {
                                "category": "diffusion",
                                "format": "safetensors",
                                "display_name": file_path.stem.replace("_", " "),
                                "file_path": resolved_str,
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
                        seen_paths.add(resolved_str)
                        discovered_models.append(
                            {
                                "category": "voice",
                                "format": "onnx",
                                "display_name": file_path.stem.replace("_", " "),
                                "file_path": resolved_str,
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
