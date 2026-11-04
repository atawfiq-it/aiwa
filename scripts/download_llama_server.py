import os
from pathlib import Path
import shutil
import stat
import subprocess
import zipfile
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "services" / "llama-cpp"
SRC_DIR = TARGET_DIR / "src"
TARGET_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_ZIP_URL = "https://github.com/ggml-org/llama.cpp/archive/refs/tags/v0.9.0.zip"


def has_tool(name: str) -> bool:
    return shutil.which(name) is not None


def build_llama_server():
    if not has_tool("cmake"):
        raise RuntimeError(
            "CMake is required to build llama-server. Install it with: sudo apt install cmake build-essential"
        )

    temp_zip = TARGET_DIR / "llama_v0.9.0_src.zip"
    print(f"⬇️  Downloading v0.9.0 source code from {SOURCE_ZIP_URL}...")

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        with client.stream("GET", SOURCE_ZIP_URL) as stream:
            if stream.status_code != 200:
                raise RuntimeError(
                    f"Failed to download source archive: HTTP {stream.status_code}"
                )
            with open(temp_zip, "wb") as f:
                for chunk in stream.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

    print("📦 Extracting source code...")
    if SRC_DIR.exists():
        shutil.rmtree(SRC_DIR)
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(temp_zip, "r") as z:
        z.extractall(SRC_DIR)
    temp_zip.unlink()

    # GitHub archives create a subfolder like 'llama.cpp-0.9.0'
    subfolders = [p for p in SRC_DIR.iterdir() if p.is_dir()]
    extracted_root = subfolders[0] if subfolders else SRC_DIR
    build_dir = extracted_root / "build"

    # Detect CUDA
    has_cuda = has_tool("nvcc")
    cmake_flags = [
        "-DCMAKE_BUILD_TYPE=Release",
    ]
    if has_cuda:
        print("⚡ NVIDIA CUDA compiler (nvcc) detected! Enabling -DGGML_CUDA=ON...")
        cmake_flags.append("-DGGML_CUDA=ON")
    else:
        print("ℹ️  No nvcc found. Compiling with CPU optimizations (-DGGML_CUDA=OFF)...")
        cmake_flags.append("-DGGML_CUDA=OFF")

    # Configure
    print("⚙️  Configuring build with CMake...")
    subprocess.run(
        ["cmake", "-B", str(build_dir), *cmake_flags],
        cwd=str(extracted_root),
        check=True,
    )

    # Compile using all available CPU threads
    cpu_count = os.cpu_count() or 4
    print(f"🔨 Compiling llama-server using {cpu_count} CPU cores...")
    subprocess.run(
        [
            "cmake",
            "--build",
            str(build_dir),
            "--config",
            "Release",
            "-j",
            str(cpu_count),
            "--target",
            "llama-server",
        ],
        cwd=str(extracted_root),
        check=True,
    )

    # Locate compiled binary
    possible_bins = [
        build_dir / "bin" / "llama-server",
        build_dir / "llama-server",
    ]
    found_bin = next((b for b in possible_bins if b.exists()), None)

    if not found_bin:
        # Search recursively in build dir
        matches = list(build_dir.glob("**/llama-server"))
        if matches:
            found_bin = matches[0]

    if not found_bin or not found_bin.exists():
        raise FileNotFoundError(
            "Build finished but 'llama-server' executable was not found."
        )

    target_bin = TARGET_DIR / "llama-server"
    shutil.copy(str(found_bin), str(target_bin))
    target_bin.chmod(
        target_bin.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR | stat.S_IXUSR
    )

    print(
        f"\n🎉 Successfully compiled and installed llama-server to:\n   {target_bin.resolve()}"
    )

    # Print version info
    res = subprocess.run([str(target_bin), "--version"], capture_output=True, text=True)
    version_output = res.stdout.strip() or res.stderr.strip()
    print(f"ℹ️  Binary info: {version_output[:120]}")


if __name__ == "__main__":
    build_llama_server()
