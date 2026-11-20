#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OS_NAME="$(uname -s)"

# 1. Source Cargo / Rust if present in ~/.cargo/bin
if [ -f "$HOME/.cargo/env" ]; then
    source "$HOME/.cargo/env"
elif [ -d "$HOME/.cargo/bin" ]; then
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 2. Source NVM / Homebrew Node if present
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    source "$NVM_DIR/nvm.sh"
elif [ -d "/opt/homebrew/bin" ]; then
    export PATH="/opt/homebrew/bin:$PATH"
fi

# 3. Verify npm and cargo
if ! command -v npm &> /dev/null; then
    echo "❌ Error: 'npm' could not be found."
    exit 1
fi
if ! command -v cargo &> /dev/null; then
    echo "❌ Error: 'cargo' could not be found."
    exit 1
fi

echo "🔍 Environment Verified ($OS_NAME):"
echo "   -> Node:  $(node --version)"
echo "   -> npm:   $(npm --version)"
echo "   -> Cargo: $(cargo --version)"

# 4. Package Sidecar
echo "📦 Step 1/3: Freezing Python backend sidecar (--onedir)..."
uv run --project "$REPO_ROOT/backend" python "$REPO_ROOT/scripts/package_sidecar.py"

# 5. Build Svelte Frontend
echo "🎨 Step 2/3: Building Svelte frontend..."
cd "$REPO_ROOT/apps/desktop"
npm run build

# 6. Build Native Installers based on OS
if [ "$OS_NAME" = "Darwin" ]; then
    echo "🍎 Step 3/3: Compiling macOS bundles (.app & .dmg)..."
    npx @tauri-apps/cli build --bundles app,dmg
elif [ "$OS_NAME" = "Linux" ]; then
    echo "🐧 Step 3/3: Compiling Linux bundles (.AppImage & .deb)..."
    npx @tauri-apps/cli build --bundles appimage,deb
else
    echo "🚀 Step 3/3: Compiling default bundle..."
    npx @tauri-apps/cli build
fi

echo ""
echo "🎉 SUCCESS: Native packages compiled in:"
echo "   $REPO_ROOT/apps/desktop/src-tauri/target/release/bundle/"