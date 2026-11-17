# ==============================================================================
# Local Multimodal AI Workstation (AIWA) - Task Runner
# ==============================================================================

# Show all available commands by default
default:
    @just --list

# ------------------------------------------------------------------------------
# 1. Installation & Environment Setup
# ------------------------------------------------------------------------------

# Install all backend Python dependencies, pre-commit hooks, and desktop Node packages
install:
    uv sync --project backend --all-extras
    uv run --project backend pre-commit install
    cd apps/desktop && npm install

# Download and install the latest official llama-server with CUDA support into services/llama-cpp/
setup-llama-server:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p services/llama-cpp
    echo "🔍 Checking for latest prebuilt llama.cpp CUDA release..."

    # Target release: Linux x64 with CUDA 12
    CUDA_ASSET_URL=$(curl -s https://api.github.com/repos/ggerganov/llama.cpp/releases/latest \
        | grep "browser_download_url" \
        | grep -i "bin-ubuntu-x64.zip" \
        | head -n 1 \
        | cut -d '"' -f 4)

    if [ -z "$CUDA_ASSET_URL" ]; then
        echo "⚠️ Could not auto-detect specific release asset. Downloading standard release..."
        CUDA_ASSET_URL=$(curl -s https://api.github.com/repos/ggerganov/llama.cpp/releases/latest \
            | grep "browser_download_url" \
            | grep -E "bin-.*-x64.zip" \
            | head -n 1 \
            | cut -d '"' -f 4)
    fi

    echo "⬇️ Downloading: $CUDA_ASSET_URL"
    curl -L "$CUDA_ASSET_URL" -o services/llama-cpp/llama-bin.zip

    echo "📦 Extracting into services/llama-cpp/..."
    unzip -o services/llama-cpp/llama-bin.zip -d services/llama-cpp/
    rm -f services/llama-cpp/llama-bin.zip

    # Locate llama-server executable (might be in root or build/bin)
    if [ -f "services/llama-cpp/llama-server" ]; then
        chmod +x services/llama-cpp/llama-server
        SERVER_BIN="$(pwd)/services/llama-cpp/llama-server"
    elif [ -f "services/llama-cpp/build/bin/llama-server" ]; then
        chmod +x services/llama-cpp/build/bin/llama-server
        SERVER_BIN="$(pwd)/services/llama-cpp/build/bin/llama-server"
    else
        SERVER_BIN="$(find $(pwd)/services/llama-cpp -name "llama-server" | head -n 1)"
        chmod +x "$SERVER_BIN"
    fi

    echo "✅ llama-server installed at: $SERVER_BIN"

    # Export or write to .env
    touch .env
    if grep -q "LLAMA_SERVER_BIN" .env; then
        sed -i "s|^LLAMA_SERVER_BIN=.*|LLAMA_SERVER_BIN=$SERVER_BIN|" .env
    else
        echo "LLAMA_SERVER_BIN=$SERVER_BIN" >> .env
    fi
    echo "📝 Updated .env with LLAMA_SERVER_BIN=$SERVER_BIN"

# ------------------------------------------------------------------------------
# 2. Code Quality & Automated Tests
# ------------------------------------------------------------------------------

# Run code formatters and linters (Ruff)
lint:
    uv run --project backend ruff check backend
    uv run --project backend ruff format --check backend

# Automatically fix linting and formatting issues
format:
    uv run --project backend ruff check --fix backend
    uv run --project backend ruff format backend

# Run the Pytest test suite
test:
    uv run --project backend pytest backend/tests

# ------------------------------------------------------------------------------
# 3. Development Servers
# ------------------------------------------------------------------------------

# Start the FastAPI backend daemon with live reloading
dev:
    uv run --project backend uvicorn app.main:app --reload --reload-dir backend/app --app-dir backend --host 127.0.0.1 --port 8000

# Start the Svelte desktop UI in local browser dev mode (http://localhost:5173)
ui-dev:
    cd apps/desktop && npm run dev

# ------------------------------------------------------------------------------
# 4. Database Migrations (Alembic + SQLModel)
# ------------------------------------------------------------------------------

# Generate a new Alembic migration revision
migrate-new message:
    cd backend && uv run alembic revision --autogenerate -m "{{message}}"

# Apply pending database migrations
migrate-up:
    cd backend && uv run alembic upgrade head

# ------------------------------------------------------------------------------
# 5. Local Model Operations & Vision Setup
# ------------------------------------------------------------------------------

# Register a local GGUF model and multimodal projector into the workstation
# register-model model mmproj="" name="Qwen3-VL-8B" ctx="4096":
#     python3 scripts/register_local_model.py \
#         --model "{{model}}" \
#         --mmproj "{{mmproj}}" \
#         --name "{{name}}" \
#         --ctx "{{ctx}}"

# ------------------------------------------------------------------------------
# 6. Production Packaging & Native Sidecar Build
# ------------------------------------------------------------------------------

# Package the FastAPI backend into a standalone native binary sidecar for Tauri
build-backend-sidecar:
    cd backend && uv run pyinstaller \
        --name aiwa-backend \
        --onefile \
        --noconfirm \
        --clean \
        --add-data "migrations:migrations" \
        app/main.py
    mkdir -p apps/desktop/src-tauri/binaries
    cp backend/dist/aiwa-backend apps/desktop/src-tauri/binaries/aiwa-backend-x86_64-unknown-linux-gnu
    chmod +x apps/desktop/src-tauri/binaries/aiwa-backend-x86_64-unknown-linux-gnu

# Build native desktop application release bundle (Tauri)
build-desktop: build-backend-sidecar
    cd apps/desktop && npm run build
    cd apps/desktop && npm run tauri build


# Download and compile llama-server (CUDA on Linux, Metal on macOS)
install-llama:
    uv run --project backend python scripts/download_llama_server.py

# Build pure C++ stable-diffusion.cpp binary
install-sd-cpp:
    uv run --project backend python scripts/setup_sd_cpp.py

# Register local GGUF model with vision projector
register-model model mmproj="" name="Qwen3-VL-8B":
    uv run --project backend python scripts/register_local_model.py --model "{{model}}" --mmproj "{{mmproj}}" --name "{{name}}"

# Package Python folder-based sidecar runtime
package-sidecar:
    uv run --project backend python scripts/package_sidecar.py

# Run both Backend and Desktop UI concurrently in one terminal
workstation:
    (trap 'kill 0' SIGINT; just dev & just ui-dev)

# Provision embedded ComfyUI and link your existing checkpoints
install-comfyui checkpoints="":
    python3 scripts/setup_comfyui.py --checkpoints "{{checkpoints}}"

# Package Python folder-based sidecar runtime
# package-sidecar:
#    python3 scripts/package_sidecar.py

# Build native Linux standalone installers (.AppImage & .deb)
package-desktop:
    bash scripts/build_desktop.sh

# Remove build files from cached git
clean-git-build:
    git rm -r --cached \
    apps/desktop/src-tauri/target/ \
    apps/desktop/src-tauri/sidecar/ \
    apps/desktop/src-tauri/binaries/ \
    apps/desktop/dist/ \
    backend/build/ \
    backend/dist/ \
    backend/*.spec \
    data/database/*.db \
    data/generated/* \
    data/uploads/* \
    data/.aiwa_session_token 2>/dev/null || true

# Clean all build generated files from git and disk
clean-all-build: clean-git-build
    rm -f apps/desktop/src-tauri/target/* \
    apps/desktop/src-tauri/sidecar/* \
    apps/desktop/src-tauri/binaries/* \
    apps/desktop/dist/* \
    backend/build/* \
    backend/dist/* \
    backend/*.spec \
    data/database/*.db \
    data/generated/* \
    data/uploads/* \
    data/.aiwa_session_token

# Completely wipe the SQLite database and re-seed fresh starter data
db-reset:
    rm -f data/database/aiwa.db data/database/aiwa.db-wal data/database/aiwa.db-shm
    just migrate-up
    uv run --project backend python -c "from app.database.seed_characters import seed_characters_if_empty; from app.database.seed_agents import seed_scenario_agents_if_empty; seed_characters_if_empty(); seed_scenario_agents_if_empty(); print('✅ Database wiped clean. Fresh starter personas and agents seeded.')"
