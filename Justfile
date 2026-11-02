default:
    @just --list

# Install all backend dependencies and pre-commit hooks
install:
    cd backend && uv sync --all-extras
    uv run pre-commit install

# Run code formatters and linters
lint:
    cd backend && uv run ruff check .
    cd backend && uv run ruff format --check .

# Automatically fix formatting and lint issues
format:
    cd backend && uv run ruff check --fix .
    cd backend && uv run ruff format .

# Run the test suite
test:
    cd backend && uv run pytest

# Launch the backend development server
dev:
    cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Generate a new Alembic migration revision
migrate-new message:
    cd backend && uv run alembic revision --autogenerate -m "{{message}}"

# Apply database migrations
migrate-up:
    cd backend && uv run alembic upgrade head