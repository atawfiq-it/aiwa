import logging
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
        """Scans multiple custom directory paths for GGUF models and matching mmproj files."""
        discovered_models: list[dict[str, Any]] = []
        mmproj_files: dict[str, Path] = {}

        valid_dirs: list[Path] = []
        for p in search_paths:
            path_obj = Path(p).resolve()
            if path_obj.exists() and path_obj.is_dir():
                valid_dirs.append(path_obj)
            else:
                logger.warning(f"Scan path does not exist or is not a directory: {p}")

        # 1. First pass: Index all multimodal projectors in all scanned directories
        for directory in valid_dirs:
            for file in directory.glob("**/*.gguf"):
                if "mmproj" in file.name.lower():
                    # Key by directory or sanitized base name
                    mmproj_files[file.stem] = file

        # 2. Second pass: Index base language & vision models
        for directory in valid_dirs:
            for file in directory.glob("**/*.gguf"):
                fname = file.name
                # Skip projector files as standalone models
                if "mmproj" in fname.lower():
                    continue

                size_bytes = file.stat().st_size
                size_gb = round(size_bytes / (1024**3), 2)
                quant = self._detect_quantization(fname)
                is_vision = self._is_vision_model(fname)

                # Attempt pairing with a suitable mmproj in the same folder or catalog
                matched_mmproj = None
                if is_vision:
                    for proj_name, proj_path in mmproj_files.items():
                        # Match models from same family (e.g. Qwen2.5-VL)
                        if "qwen" in fname.lower() and "qwen" in proj_name.lower():
                            matched_mmproj = str(proj_path)
                            break
                        elif proj_path.parent == file.parent:
                            matched_mmproj = str(proj_path)
                            break

                display_name = (
                    file.stem.replace("-Q4_K_M", "").replace(".Q4_K_M", "").replace("_", " ")
                )

                discovered_models.append(
                    {
                        "display_name": display_name,
                        "file_path": str(file.resolve()),
                        "file_size_gb": size_gb,
                        "file_size_bytes": size_bytes,
                        "quantization": quant,
                        "vision_supported": is_vision and matched_mmproj is not None,
                        "mmproj_path": matched_mmproj,
                        "parent_directory": str(directory),
                    }
                )

        return discovered_models


model_scanner = ModelScannerService()
