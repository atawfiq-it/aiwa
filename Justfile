export UV_LINK_MODE := "copy"

default:
    @just --list

# Install all backend dependencies and pre-commit hooks
install:
    uv sync --project backend --all-extras
    uv run --project backend pre-commit install
    cd apps/desktop && npm install

# Launch desktop UI in web dev mode
ui-dev:
    cd apps/desktop && npm run dev

# Run code formatters and linters
lint:
    uv run --project backend ruff check backend
    uv run --project backend ruff format --check backend

# Automatically fix formatting and lint issues
format:
    uv run --project backend ruff check --fix backend
    uv run --project backend ruff format backend

# Run the test suite
test:
    uv run --project backend pytest backend/tests

# Launch the backend development server
dev:
    uv run --project backend uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000

# Generate a new Alembic migration revision
migrate-new message:
    cd backend && uv run alembic revision --autogenerate -m "{{message}}"

# Apply database migrations
migrate-up:
    cd backend && uv run alembic upgrade head

# Package backend into a standalone native binary sidecar
build-backend-sidecar:
    cd backend && uv run pyinstaller \
        --name aiwa-backend \
        --onefile \
        --noconfirm \
        --clean \
        --add-data "migrations:migrations" \
        app/main.py
    # Copy compiled binary into Tauri external binaries directory
    mkdir -p apps/desktop/src-tauri/binaries
    cp backend/dist/aiwa-backend apps/desktop/src-tauri/binaries/aiwa-backend-x86_64-unknown-linux-gnu

# Build native desktop application release
build-desktop: build-backend-sidecar
    cd apps/desktop && npm run build
    cd apps/desktop && npm run tauri build
