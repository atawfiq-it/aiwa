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
        return any(
            k in lower
            for k in ["-vl", "vision", "llava", "qwen-vl", "qwen2-vl", "qwen2.5-vl", "qwen3-vl"]
        )

    def scan_directories(self, search_paths: list[str]) -> list[dict[str, Any]]:
        """Deep recursive scan across all sub-directory levels for GGUF, MLX, Diffusion, and Voice models."""
        discovered_models: list[dict[str, Any]] = []
        mmproj_files: dict[str, Path] = {}
        seen_paths = set()

        valid_dirs: list[Path] = []
        for p in search_paths:
            path_obj = Path(p).resolve()
            if path_obj.exists() and path_obj.is_dir():
                valid_dirs.append(path_obj)
            else:
                logger.warning(f"Scan path does not exist: {p}")

        # Pass 1: Recursive indexing of multimodal projectors (.gguf)
        for root_dir in valid_dirs:
            for root, _, files in os.walk(root_dir, followlinks=True):
                for f in files:
                    if f.lower().endswith(".gguf") and "mmproj" in f.lower():
                        proj_path = Path(root) / f
                        if proj_path.is_file():
                            mmproj_files[proj_path.stem] = proj_path

        # Pass 2: Recursive indexing of MLX bundles, GGUFs, Diffusion checkpoints, and Voice models
        for root_dir in valid_dirs:
            for root, _, files in os.walk(root_dir, followlinks=True):
                root_path = Path(root)

                # 1. Detect Apple MLX / Transformer LLM Folder Bundle
                # A directory with config.json + tokenizer + *.safetensors is ALWAYS an LLM/VLM, never Diffusion
                has_config = "config.json" in files
                has_tokenizer = "tokenizer.json" in files or "tokenizer_config.json" in files
                safetensor_shards = [f for f in files if f.lower().endswith(".safetensors")]
                is_mlx_folder = has_config and has_tokenizer and len(safetensor_shards) > 0

                if is_mlx_folder:
                    resolved_dir = str(root_path.resolve())
                    if resolved_dir not in seen_paths:
                        total_bytes = sum(
                            (root_path / s).stat().st_size
                            for s in safetensor_shards
                            if (root_path / s).is_file()
                        )
                        if total_bytes > 50 * 1024 * 1024:
                            seen_paths.add(resolved_dir)
                            is_vision = (
                                "preprocessor_config.json" in files
                                or "video_preprocessor_config.json" in files
                                or self._is_vision_model(root_path.name)
                            )
                            discovered_models.append(
                                {
                                    "category": "llm",
                                    "format": "mlx",
                                    "display_name": root_path.name,
                                    "file_path": resolved_dir,
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

                # 2. Scan individual files inside this folder (allows co-located .gguf or .safetensors)
                for f in files:
                    file_path = root_path / f
                    fname_lower = f.lower()

                    if not file_path.is_file() or file_path.is_dir():
                        continue

                    resolved_file = str(file_path.resolve())
                    if resolved_file in seen_paths:
                        continue

                    # A. GGUF Language / Vision Models
                    if fname_lower.endswith(".gguf"):
                        if "mmproj" in fname_lower:
                            continue

                        size_bytes = file_path.stat().st_size
                        if size_bytes < 50 * 1024 * 1024:
                            continue

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

                        seen_paths.add(resolved_file)
                        discovered_models.append(
                            {
                                "category": "llm",
                                "format": "gguf",
                                "display_name": file_path.stem.replace("-Q4_K_M", "").replace(
                                    "_", " "
                                ),
                                "file_path": resolved_file,
                                "file_size_gb": round(size_bytes / (1024**3), 2),
                                "file_size_bytes": size_bytes,
                                "quantization": self._detect_quantization(f),
                                "vision_supported": is_vision and matched_mmproj is not None,
                                "mmproj_path": matched_mmproj,
                                "directory": str(root),
                            }
                        )

                    # B. Image Diffusion Checkpoints (.safetensors, .ckpt)
                    elif fname_lower.endswith((".safetensors", ".ckpt")):
                        # Never classify shards inside an MLX/LLM folder as Diffusion
                        if is_mlx_folder:
                            continue

                        size_bytes = file_path.stat().st_size
                        if size_bytes < 500 * 1024 * 1024:
                            continue

                        if fname_lower.endswith(".safetensors"):
                            if inspect_safetensors_type(file_path) != "diffusion":
                                continue

                        seen_paths.add(resolved_file)
                        discovered_models.append(
                            {
                                "category": "diffusion",
                                "format": "safetensors",
                                "display_name": file_path.stem.replace("_", " "),
                                "file_path": resolved_file,
                                "file_size_gb": round(size_bytes / (1024**3), 2),
                                "file_size_bytes": size_bytes,
                                "quantization": "fp16" if "fp16" in fname_lower else "fp32",
                                "vision_supported": False,
                                "mmproj_path": None,
                                "directory": str(root),
                            }
                        )

                    # C. Voice / Speech Models (.onnx, .bin)
                    elif fname_lower.endswith((".onnx", ".bin")) and any(
                        k in fname_lower for k in ["whisper", "kokoro", "tts", "stt", "voice"]
                    ):
                        size_bytes = file_path.stat().st_size
                        seen_paths.add(resolved_file)
                        discovered_models.append(
                            {
                                "category": "voice",
                                "format": "onnx",
                                "display_name": file_path.stem.replace("_", " "),
                                "file_path": resolved_file,
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
