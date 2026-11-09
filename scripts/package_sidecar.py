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
if ARCH == "x86_64":
    TARGET_TRIPLE = "x86_64-unknown-linux-gnu"
elif ARCH in ["aarch64", "arm64"]:
    TARGET_TRIPLE = "aarch64-unknown-linux-gnu"
else:
    TARGET_TRIPLE = f"{ARCH}-unknown-linux-gnu"


def build_folder_sidecar():
    print(f"📦 Packaging folder-based backend sidecar for target: {TARGET_TRIPLE}...")

    # 1. Run PyInstaller in --onedir mode
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
        str(BACKEND_DIR / "app" / "main.py"),
    ]

    subprocess.run(cmd, cwd=str(BACKEND_DIR), check=True)

    # 2. Deploy the folder-based runtime into Tauri resources
    dist_folder = BACKEND_DIR / "dist" / "aiwa-backend-app"
    if not dist_folder.exists():
        raise FileNotFoundError(
            f"PyInstaller failed to output directory at {dist_folder}"
        )

    if SIDECAR_DIR.exists():
        shutil.rmtree(SIDECAR_DIR)
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)

    print(f"📂 Copying backend runtime folder into {SIDECAR_DIR}...")
    shutil.copytree(dist_folder, SIDECAR_DIR / "runtime", dirs_exist_ok=True)

    # 3. Create the launcher wrapper in src-tauri/binaries/
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    launcher_path = BINARIES_DIR / f"aiwa-backend-{TARGET_TRIPLE}"

    launcher_script = """#!/usr/bin/env bash
# AIWA Folder-based Sidecar Entrypoint Launcher
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
RESOURCE_DIR="$DIR/../sidecar/runtime"

if [ -f "$RESOURCE_DIR/aiwa-backend-app" ]; then
    exec "$RESOURCE_DIR/aiwa-backend-app" "$@"
else
    # Fallback to local dev path
    exec "$DIR/aiwa-backend-app" "$@"
fi
"""

    with open(launcher_path, "w") as f:
        f.write(launcher_script)

    # Make launcher executable (chmod +x)
    launcher_path.chmod(
        launcher_path.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR | stat.S_IXUSR
    )

    # Also copy the primary executable directly alongside the launcher
    shutil.copy(dist_folder / "aiwa-backend-app", BINARIES_DIR / "aiwa-backend-app")

    print("✅ Folder-based sidecar successfully staged:")
    print(f"   -> Runtime directory: {SIDECAR_DIR / 'runtime'}")
    print(f"   -> Launcher binary:   {launcher_path}")


if __name__ == "__main__":
    build_folder_sidecar()
