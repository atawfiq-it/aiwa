# Local Multimodal AI Workstation (AIWA)

# To update uv dependencies
uv sync --project backend --all-extras

# Running app
#### First Time Only ###
cd apps/desktop
npm install
cd ../..
#### Normal Running ###
just dev
# From another terminal
just ui-dev
#  ➜  Local:   http://localhost:5173/
#  ➜  Network: use --host to expose

# Database Migration
just migrate-new "......."
just migrate-up

# Format and Test
just format
just test

# Fix file formatting for all
uv run --project backend pre-commit run --all-files
