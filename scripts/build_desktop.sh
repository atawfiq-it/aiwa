#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_DIR="$REPO_ROOT/apps/desktop/src-tauri"
BUNDLE_DIR="$TAURI_DIR/target/release/bundle"

# 1. Environment exports
export APPIMAGE_EXTRACT_AND_RUN=1

if [ -f "$HOME/.cargo/env" ]; then
    source "$HOME/.cargo/env"
elif [ -d "$HOME/.cargo/bin" ]; then
    export PATH="$HOME/.cargo/bin:$PATH"
fi

export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    source "$NVM_DIR/nvm.sh"
elif [ -s "/usr/local/share/nvm/nvm.sh" ]; then
    source "/usr/local/share/nvm/nvm.sh"
fi

# 2. Package Python Sidecar
echo "📦 Step 1/4: Freezing Python backend sidecar..."
python3 "$REPO_ROOT/scripts/package_sidecar.py"

# 3. Build Svelte Frontend
echo "🎨 Step 2/4: Building Svelte frontend..."
cd "$REPO_ROOT/apps/desktop"
npm run build

# 4. Build Native Debian Package with Tauri (bypasses linuxdeploy)
echo "🚀 Step 3/4: Building Debian package (.deb)..."
npx @tauri-apps/cli build --bundles deb

# 5. Build Standalone AppImage directly with appimagetool
echo "📦 Step 4/4: Generating standalone .AppImage..."
mkdir -p "$BUNDLE_DIR/appimage"
APP_DIR="/tmp/aiwa_appimage_root"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin" "$APP_DIR/usr/lib/aiwa" "$APP_DIR/usr/share/icons/hicolor/256x256/apps"

# Copy binary & assets from release build
cp "$TAURI_DIR/target/release/aiwa" "$APP_DIR/usr/bin/aiwa"
cp -r "$TAURI_DIR/sidecar" "$APP_DIR/usr/lib/aiwa/"
cp -r "$TAURI_DIR/binaries" "$APP_DIR/usr/lib/aiwa/"
cp "$TAURI_DIR/icons/128x128@2x.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/aiwa.png"
cp "$TAURI_DIR/icons/128x128@2x.png" "$APP_DIR/aiwa.png"

# AppRun launcher script
cat << 'EOF' > "$APP_DIR/AppRun"
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="$HERE/usr/bin:$HERE/usr/lib/aiwa/binaries:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/lib:$HERE/usr/lib/aiwa/sidecar/runtime:$LD_LIBRARY_PATH"
exec "$HERE/usr/bin/aiwa" "$@"
EOF
chmod +x "$APP_DIR/AppRun"

# Desktop Entry
cat << EOF > "$APP_DIR/aiwa.desktop"
[Desktop Entry]
Name=AIWA
Exec=aiwa
Icon=aiwa
Type=Application
Categories=Development;Utility;
Comment=Local Multimodal AI Workstation
Terminal=false
EOF
chmod +x "$APP_DIR/aiwa.desktop"

# Run appimagetool
ARCH=x86_64 appimagetool "$APP_DIR" "$BUNDLE_DIR/appimage/AIWA_0.1.0_amd64.AppImage"
rm -rf "$APP_DIR"

echo ""
echo "🎉 SUCCESS: Desktop packages compiled successfully:"
echo "   -> Debian Package:  $BUNDLE_DIR/deb/aiwa_0.1.0_amd64.deb"
echo "   -> Standalone App:  $BUNDLE_DIR/appimage/AIWA_0.1.0_amd64.AppImage"
