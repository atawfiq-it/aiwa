```
# Third-Party Software & Model Notices

AIWA ("AI Workspace App") integrates with and orchestrates several open-source libraries, C++ runtimes, and community-trained AI models. Each third-party component remains subject to its respective license:

## Core Frameworks & Infrastructure
* **FastAPI / Starlette / Pydantic / SQLModel / Alembic**: MIT License
* **Tauri (v2) / Svelte / Tailwind CSS / Marked / Highlight.js**: MIT / Apache-2.0 Licenses
* **LanceDB & FastEmbed**: Apache-2.0 License
* **uv**: Apache-2.0 / MIT Dual License

## Local AI Runtimes & Media Engines
* **llama.cpp** (`ggerganov/llama.cpp` / `ggml-org/llama.cpp`): MIT License
* **Apple MLX / mlx-lm / mlx-vlm**: MIT License
* **stable-diffusion.cpp** (`leejet/stable-diffusion.cpp`): MIT License
* **Hugging Face Diffusers / Transformers / Accelerate / Safetensors**: Apache-2.0 License
* **Faster-Whisper**: MIT License
* **Kokoro TTS**: Apache-2.0 License
* **ComfyUI** (Optional external integration): GPL-3.0 License

## Document Processing Notice
* **PyMuPDF / PyMuPDF4LLM** (Artifex Software): Dual-licensed under **AGPL-3.0** and commercial license. If you distribute a commercial closed-source derivative incorporating PyMuPDF, please review Artifex's licensing terms or swap the extraction adapter for an Apache/MIT PDF parser (e.g., `pypdf` or `pdfplumber`).

## Model Weights
Downloaded GGUF, MLX, and Safetensors model weights (such as Qwen, Llama, Mistral, SDXL-Turbo, and Stable Diffusion) are NOT bundled in this repository and are governed by the license agreements published by their respective creators on Hugging Face.
```