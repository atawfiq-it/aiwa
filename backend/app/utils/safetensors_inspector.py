import json
import struct
from pathlib import Path
from typing import Literal


def inspect_safetensors_type(
    file_path: Path,
) -> Literal["diffusion", "llm", "unknown"]:
    """Reads the binary JSON header of a .safetensors file to classify Diffusion vs LLM."""
    try:
        with open(file_path, "rb") as f:
            header_size_bytes = f.read(8)
            if len(header_size_bytes) < 8:
                return "unknown"

            header_len = struct.unpack("<Q", header_size_bytes)[0]
            if header_len > 10 * 1024 * 1024:  # Cap at 10MB
                return "unknown"

            header_raw = f.read(header_len).decode("utf-8", errors="ignore")
            header_json = json.loads(header_raw)

            # Inspect ALL keys so visual blocks don't mask language_model layers
            all_keys = " ".join(header_json.keys()).lower()

            # Image Diffusion Signatures (SD1.5 / SDXL / Flux)
            if any(
                sig in all_keys
                for sig in [
                    "model.diffusion_model",
                    "first_stage_model",
                    "cond_stage_model",
                    "double_blocks",
                    "single_blocks",
                ]
            ):
                return "diffusion"

            # Language & Vision-Language Signatures (Qwen2/3-VL, Llama, Mistral, MLX)
            if any(
                sig in all_keys
                for sig in [
                    "model.layers",
                    "language_model",
                    "lm_head",
                    "embed_tokens",
                    "vision_tower",
                    "visual.blocks",
                ]
            ):
                return "llm"

            return "unknown"
    except Exception:
        return "unknown"
