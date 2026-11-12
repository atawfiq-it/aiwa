from pathlib import Path
import platform
import shutil
import stat
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
TAURI_DIR = REPO_ROOT / "apps" / "desktop" / "src-tauri"
SIDECAR_DIR = TAURI_DIR / "sidecar"
BINARIES_DIR = TAURI_DIR / "binaries"

# Determine target architecture triple for Linux
ARCH = platform.machine()
ARCH = platform.machine()
if ARCH == "x86_64":
    TARGET_TRIPLE = "x86_64-unknown-linux-gnu"
elif ARCH in ["aarch64", "arm64"]:
    TARGET_TRIPLE = "aarch64-unknown-linux-gnu"
else:
    TARGET_TRIPLE = f"{ARCH}-unknown-linux-gnu"


def build_sidecar():
    print(f"📦 Packaging folder-based backend sidecar for {TARGET_TRIPLE}...")

    # Run PyInstaller in --onedir mode
    cmd = [
        "uv",
        "run",
        "--project",
        str(BACKEND_DIR),
        "pyinstaller",
        "--name",
        "aiwa-backend-app",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--add-data",
        f"{BACKEND_DIR / 'migrations'}:migrations",
        "--hidden-import",
        "sqlmodel",
        "--hidden-import",
        "uvicorn",
        "--hidden-import",
        "sqlite3",
        "--hidden-import",
        "engineio.async_drivers.asgi",
        "--collect-all",
        "triton",  # Ensures libtriton.so is explicitly collected
        str(BACKEND_DIR / "app" / "main.py"),
    ]

    subprocess.run(cmd, cwd=str(BACKEND_DIR), check=True)

    dist_folder = BACKEND_DIR / "dist" / "aiwa-backend-app"
    if not dist_folder.exists():
        raise FileNotFoundError(f"PyInstaller build failed at {dist_folder}")

    # Copy runtime folder into Tauri resources
    if SIDECAR_DIR.exists():
        shutil.rmtree(SIDECAR_DIR)
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)

    print(f"📂 Copying runtime distribution into {SIDECAR_DIR / 'runtime'}...")
    shutil.copytree(dist_folder, SIDECAR_DIR / "runtime", dirs_exist_ok=True)

    # Create target launcher script in src-tauri/binaries/
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    launcher_path = BINARIES_DIR / f"aiwa-backend-{TARGET_TRIPLE}"

    launcher_script = """#!/usr/bin/env bash
# AIWA Folder-Based Sidecar Entrypoint Launcher
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
RESOURCE_DIR="$DIR/../sidecar/runtime"

if [ -f "$RESOURCE_DIR/aiwa-backend-app" ]; then
    exec "$RESOURCE_DIR/aiwa-backend-app" "$@"
else
    exec "$DIR/aiwa-backend-app" "$@"
fi
"""

    with open(launcher_path, "w") as f:
        f.write(launcher_script)

    launcher_path.chmod(
        launcher_path.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR | stat.S_IXUSR
    )
    shutil.copy(dist_folder / "aiwa-backend-app", BINARIES_DIR / "aiwa-backend-app")

    print("✅ Folder-based sidecar packaged successfully.")


if __name__ == "__main__":
    build_sidecar()
