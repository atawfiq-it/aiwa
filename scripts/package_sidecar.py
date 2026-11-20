import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
TAURI_DIR = REPO_ROOT / "apps" / "desktop" / "src-tauri"
SIDECAR_DIR = TAURI_DIR / "sidecar"
BINARIES_DIR = TAURI_DIR / "binaries"


def get_target_triple() -> str:
    sys_name = platform.system()
    arch = platform.machine().lower()

    if sys_name == "Windows":
        if arch in ["amd64", "x86_64"]:
            return "x86_64-pc-windows-msvc"
        elif arch in ["arm64", "aarch64"]:
            return "aarch64-pc-windows-msvc"
    elif sys_name == "Darwin":
        if arch in ["arm64", "aarch64"]:
            return "aarch64-apple-darwin"
        return "x86_64-apple-darwin"
    else:  # Linux
        if arch in ["arm64", "aarch64"]:
            return "aarch64-unknown-linux-gnu"
        return "x86_64-unknown-linux-gnu"

    return f"{arch}-unknown-{sys_name.lower()}"


def build_windows_exe_launcher(launcher_dest: Path) -> None:
    """Compiles a tiny native Rust .exe wrapper to launch the folder-based runtime on Windows."""
    if not shutil.which("rustc"):
        raise RuntimeError(
            "rustc is required on Windows to compile the native sidecar launcher."
        )

    launcher_rs = BINARIES_DIR / "launcher_tmp.rs"
    rust_code = """
use std::env;
use std::process::Command;

fn main() {
    let exe_dir = env::current_exe().unwrap().parent().unwrap().to_path_buf();
    let resource_bin = exe_dir.join("..").join("sidecar").join("runtime").join("aiwa-backend-app.exe");
    let local_bin = exe_dir.join("aiwa-backend-app.exe");
    let target = if resource_bin.exists() { resource_bin } else { local_bin };

    let args: Vec<String> = env::args().skip(1).collect();
    let status = Command::new(target)
        .args(args)
        .status()
        .expect("Failed to launch AIWA backend runtime");

    std::process::exit(status.code().unwrap_or(1));
}
"""
    launcher_rs.write_text(rust_code, encoding="utf-8")
    try:
        subprocess.run(
            ["rustc", "-O", str(launcher_rs), "-o", str(launcher_dest)],
            check=True,
        )
    finally:
        if launcher_rs.exists():
            launcher_rs.unlink()


def copy_windows_cuda_dlls(runtime_dir: Path) -> None:
    """Bundles NVIDIA CUDA runtime DLLs into the Windows sidecar if CUDA Toolkit is installed."""
    cuda_path = os.environ.get("CUDA_PATH")
    if not cuda_path:
        return

    cuda_bin = Path(cuda_path) / "bin"
    if not cuda_bin.exists():
        return

    print(f"⚡ Scanning {cuda_bin} for required CUDA DLLs...")
    for pattern in ["cudart64_*.dll", "cublas64_*.dll", "cublasLt64_*.dll"]:
        for dll in cuda_bin.glob(pattern):
            dest = runtime_dir / dll.name
            if not dest.exists():
                shutil.copy2(dll, dest)
                print(f"   -> Bundled {dll.name}")


def build_sidecar():
    system = platform.system()
    target_triple = get_target_triple()
    is_windows = system == "Windows"
    data_sep = ";" if is_windows else ":"

    print(f"📦 Packaging folder-based sidecar for {system} ({target_triple})...")

    cmd = [
        "uv", "run", "--project", str(BACKEND_DIR),
        "pyinstaller",
        "--name", "aiwa-backend-app",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--add-data", f"{BACKEND_DIR / 'migrations'}{data_sep}migrations",
        "--hidden-import", "sqlmodel",
        "--hidden-import", "uvicorn",
        "--hidden-import", "sqlite3",
        "--hidden-import", "engineio.async_drivers.asgi",
        "--hidden-import", "yaml",
        str(BACKEND_DIR / "app" / "main.py"),
    ]

    subprocess.run(cmd, cwd=str(BACKEND_DIR), check=True)

    dist_folder = BACKEND_DIR / "dist" / "aiwa-backend-app"
    if not dist_folder.exists():
        raise FileNotFoundError(f"PyInstaller failed to create directory: {dist_folder}")

    if SIDECAR_DIR.exists():
        shutil.rmtree(SIDECAR_DIR)
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)

    runtime_dest = SIDECAR_DIR / "runtime"
    print(f"📂 Copying backend runtime folder into {runtime_dest}...")
    shutil.copytree(dist_folder, runtime_dest, dirs_exist_ok=True)

    BINARIES_DIR.mkdir(parents=True, exist_ok=True)

    if is_windows:
        copy_windows_cuda_dlls(runtime_dest)
        launcher_path = BINARIES_DIR / f"aiwa-backend-{target_triple}.exe"
        print(f"🔨 Compiling Windows sidecar wrapper: {launcher_path.name}...")
        build_windows_exe_launcher(launcher_path)
        shutil.copy(dist_folder / "aiwa-backend-app.exe", BINARIES_DIR / "aiwa-backend-app.exe")
    else:
        launcher_path = BINARIES_DIR / f"aiwa-backend-{target_triple}"
        launcher_script = f"""#!/usr/bin/env bash
DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" >/dev/null 2>&1 && pwd)"
RESOURCE_DIR="$DIR/../sidecar/runtime"

if [ -f "$RESOURCE_DIR/aiwa-backend-app" ]; then
    exec "$RESOURCE_DIR/aiwa-backend-app" "$@"
else
    exec "$DIR/aiwa-backend-app" "$@"
fi
"""
        launcher_path.write_text(launcher_script, encoding="utf-8")
        launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR | stat.S_IXUSR)
        shutil.copy(dist_folder / "aiwa-backend-app", BINARIES_DIR / "aiwa-backend-app")

    print("\n✅ Folder-based sidecar staged successfully:")
    print(f"   -> Runtime Folder: {runtime_dest}")
    print(f"   -> Sidecar Entry:  {launcher_path}")


if __name__ == "__main__":
    build_sidecar()