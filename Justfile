default:
    @just --list

# ==========================================
# Setup & Dependencies
# ==========================================

# Install all backend, audio, and desktop frontend dependencies
install:
    uv sync --project backend --all-extras
    uv run --project backend pre-commit install
    cd apps/desktop && npm install

# Download and compile llama-server (Metal on macOS, CUDA/ROCm/Vulkan/CPU on Linux)
install-llama:
    uv run --project backend python scripts/download_llama_server.py

# Build pure C++ stable-diffusion.cpp binary
install-sd-cpp:
    uv run --project backend python scripts/setup_sd_cpp.py

# Provision embedded ComfyUI and link existing checkpoints
install-comfyui checkpoints="":
    uv run --project backend python scripts/setup_comfyui.py --checkpoints "{{checkpoints}}"

# ==========================================
# Code Quality & Testing
# ==========================================

# Run code linters and formatting checks
lint:
    uv run --project backend ruff check backend
    uv run --project backend ruff format --check backend

# Automatically fix lint issues and format code
format:
    uv run --project backend ruff check --fix backend
    uv run --project backend ruff format backend

# Run the backend automated test suite
test:
    uv run --project backend pytest backend/tests

# Run comprehensive system, GPU/Metal, and path diagnostics
doctor:
    uv run --project backend python -c "import torch, shutil, sys; from pathlib import Path; from app.supervisors.vram_arbiter import vram_arbiter; from app.supervisors.hardware_probe import hardware_probe; from app.core.config import settings; print('=== AIWA SYSTEM DIAGNOSTICS ==='); print('Python:', sys.version.split()[0]); print('Hardware:', hardware_probe.detect_accelerator()); print('Memory Arbiter:', vram_arbiter.get_vram_status()); print('llama-server:', 'FOUND' if Path(settings.LLAMA_SERVER_BIN).exists() or shutil.which('llama-server') else 'MISSING'); print('Database:', 'FOUND' if (settings.DATABASE_DIR / 'aiwa.db').exists() else 'NEW'); print('LLM Paths:', [str(p) for p in settings.get_llm_search_paths()]); print('Diffusion Paths:', [str(p) for p in settings.get_diffusion_search_paths()]); print('================================')"

# ==========================================
# Development Execution
# ==========================================

# Launch the FastAPI backend daemon (respects .env API_HOST & API_PORT + Port Reclamation)
dev:
    cd backend && uv run python -m app.main

# Launch the Svelte desktop UI dev server
ui-dev:
    cd apps/desktop && npm run dev

# Run both Backend and Desktop UI concurrently in one terminal
workstation:
    (trap 'kill 0' SIGINT; just dev & just ui-dev)

# ==========================================
# Database Migrations (Alembic)
# ==========================================

# Generate a new Alembic migration revision
migrate-new message:
    cd backend && uv run alembic revision --autogenerate -m "{{message}}"

# Apply all pending database migrations
migrate-up:
    cd backend && uv run alembic upgrade head

# ==========================================
# Model & Feature Testing Helpers
# ==========================================

# Register and load a local GGUF model with optional vision projector
register-model model mmproj="" name="Qwen2.5-VL-7B":
    uv run --project backend python scripts/register_local_model.py --model "{{model}}" --mmproj "{{mmproj}}" --name "{{name}}"

# Run end-to-end document-to-audio briefing test
test-briefing pdf style="bullet" voice="af_heart":
    uv run --project backend python scripts/test_audio_briefing.py --pdf "{{pdf}}" --style "{{style}}" --voice "{{voice}}"

# Verify GBNF grammar constrained JSON output
test-grammar:
    uv run --project backend python scripts/test_gbnf.py

# ==========================================
# Native Desktop Packaging (macOS, Linux, Windows)
# ==========================================

# Freeze the Python folder-based sidecar (--onedir)
package-sidecar:
    uv run --project backend python scripts/package_sidecar.py

# Build native OS desktop bundles (macOS .app/.dmg or Linux .AppImage/.deb)
package-desktop:
    bash scripts/build_desktop.sh

# Build Windows desktop installers (.exe NSIS & .msi) - Run on Windows PowerShell
package-windows:
    powershell -ExecutionPolicy Bypass -File scripts/package_windows.ps1
