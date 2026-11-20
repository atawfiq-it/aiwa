import os
from pathlib import Path
import shutil
import stat
import subprocess
import zipfile
import httpx
import platform

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "services" / "llama-cpp"
SRC_DIR = TARGET_DIR / "src"
TARGET_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_ZIP_URL = "https://github.com/ggml-org/llama.cpp/archive/refs/tags/v0.9.0.zip"

# Ensure CUDA paths are included in system PATH
CUDA_PATHS = ["/usr/local/cuda/bin", "/usr/local/cuda-12/bin", "/opt/cuda/bin"]
for cp in CUDA_PATHS:
    if Path(cp).exists() and cp not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{cp}:{os.environ.get('PATH', '')}"


def has_tool(name: str) -> bool:
    return shutil.which(name) is not None


def build_llama_server():
    if not has_tool("cmake"):
        raise RuntimeError(
            "CMake is required. Install with: sudo apt install cmake build-essential"
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

    subfolders = [p for p in SRC_DIR.iterdir() if p.is_dir()]
    extracted_root = subfolders[0] if subfolders else SRC_DIR
    build_dir = extracted_root / "build"

    system = platform.system()
    machine = platform.machine()
    env_accel = os.environ.get("AIWA_HARDWARE_ACCELERATION", "auto").lower()

    cmake_flags = ["-DCMAKE_BUILD_TYPE=Release"]

    if env_accel == "metal" or (env_accel == "auto" and system == "Darwin" and machine == "arm64"):
        print("🍎 Enabling Apple Metal GPU acceleration (-DGGML_METAL=ON)...")
        cmake_flags.extend(["-DGGML_METAL=ON", "-DGGML_METAL_EMBED_LIBRARY=ON"])

    elif env_accel == "cuda" or (env_accel == "auto" and has_tool("nvcc")):
        print("⚡ Enabling NVIDIA CUDA acceleration (-DGGML_CUDA=ON)...")
        cmake_flags.append("-DGGML_CUDA=ON")

    elif env_accel == "rocm" or (env_accel == "auto" and (os.path.exists("/dev/kfd") or has_tool("hipcc"))):
        print("🔴 Enabling AMD ROCm/HIP acceleration (-DGGML_HIP=ON)...")
        cmake_flags.append("-DGGML_HIP=ON")

    elif env_accel == "vulkan" or (env_accel == "auto" and has_tool("vulkaninfo")):
        print("🌋 Enabling Cross-Vendor Vulkan acceleration (-DGGML_VULKAN=ON)...")
        cmake_flags.append("-DGGML_VULKAN=ON")

    else:
        print("💻 Configuring Universal CPU SIMD build (-DGGML_NATIVE=ON)...")
        cmake_flags.append("-DGGML_NATIVE=ON")

    print("⚙️  Configuring CMake...")
    subprocess.run(
        ["cmake", "-B", str(build_dir), *cmake_flags],
        cwd=str(extracted_root),
        check=True,
    )

    cpu_count = os.cpu_count() or 4
    print(f"🔨 Compiling llama-server with {cpu_count} CPU cores...")
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

    possible_bins = [build_dir / "bin" / "llama-server", build_dir / "llama-server"]
    found_bin = next((b for b in possible_bins if b.exists()), None)
    if not found_bin:
        matches = list(build_dir.glob("**/llama-server"))
        if matches:
            found_bin = matches[0]

    target_bin = TARGET_DIR / "llama-server"
    shutil.copy(str(found_bin), str(target_bin))
    target_bin.chmod(
        target_bin.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR | stat.S_IXUSR
    )

    print(f"\n🎉 Compiled native llama-server to: {target_bin.resolve()}")


if __name__ == "__main__":
    build_llama_server()
