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

# Run QWEN Model
# Terminal 1 #
just dev
# Terminal 2 #
just register-model \
  "/path/to/Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf" \
  "/path/to/mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf" \
  "Qwen2.5-VL-7B-Instruct"
# OR
python3 scripts/register_local_model.py \
  --model "/path/to/model.gguf" \
  --mmproj "/path/to/mmproj.gguf" \
  --name "Qwen2.5-VL-7B" \
  --ctx 2048
