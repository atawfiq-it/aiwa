# Local Multimodal AI Workstation (AIWA)

# To update uv dependencies
uv sync --project backend --all-extras

# Running app
cd apps/desktop
npm install
cd ../..
just dev
# From another terminal
just ui-dev
#  ➜  Local:   http://localhost:5173/
#  ➜  Network: use --host to expose
