import os
from pathlib import Path
import shutil
import stat
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
SD_DIR = REPO_ROOT / "services" / "diffusion-cpp"
SD_SRC = SD_DIR / "src"
SD_DIR.mkdir(parents=True, exist_ok=True)


def setup_sd_cpp():
    print("📦 Cloning leejet/stable-diffusion.cpp into services/diffusion-cpp/src...")
    if not (SD_SRC / ".git").exists():
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/leejet/stable-diffusion.cpp.git",
                str(SD_SRC),
            ],
            check=True,
        )
    else:
        subprocess.run(["git", "-C", str(SD_SRC), "pull"], check=True)

    print("🔗 Fetching git submodules (ggml)...")
    subprocess.run(
        ["git", "-C", str(SD_SRC), "submodule", "update", "--init", "--recursive"],
        check=True,
    )

    build_dir = SD_SRC / "build"
    has_cuda = shutil.which("nvcc") is not None

    # Enable all examples so the CLI tool is built
    cmake_flags = [
        "-DCMAKE_BUILD_TYPE=Release",
        "-DSD_BUILD_EXAMPLES=ON",
    ]

    if has_cuda:
        print("⚡ NVIDIA CUDA detected! Configuring -DSD_CUDA=ON...")
        cmake_flags.append("-DSD_CUDA=ON")
    else:
        print("ℹ️  Compiling CPU-only stable-diffusion.cpp...")

    print("⚙️  Configuring CMake build...")
    subprocess.run(
        ["cmake", "-B", str(build_dir), *cmake_flags], cwd=str(SD_SRC), check=True
    )

    # Clean previous build artifacts to ensure fresh compilation
    print("🔨 Compiling all targets in stable-diffusion.cpp...")
    cpu_count = os.cpu_count() or 4
    subprocess.run(
        [
            "cmake",
            "--build",
            str(build_dir),
            "--config",
            "Release",
            "-j",
            str(cpu_count),
        ],
        cwd=str(SD_SRC),
        check=True,
    )

    # Search for any real ELF executable generated in build/bin or build/
    found = None
    candidates = []

    for path in build_dir.rglob("*"):
        # Check for real ELF binary executable on Linux
        if path.is_file() and not path.name.endswith(
            (".txt", ".cmake", ".o", ".a", ".so")
        ):
            try:
                with open(path, "rb") as f:
                    header = f.read(4)
                    if header == b"\x7fELF":
                        candidates.append(path)
            except Exception:
                pass

    print(f"🔍 Discovered compiled executable binaries: {[c.name for c in candidates]}")

    # Prioritize 'sd', 'stable-diffusion', or whatever main binary was generated
    for c in candidates:
        if c.name in ["sd", "stable-diffusion", "sd-cli", "cli"]:
            found = c
            break

    if not found and candidates:
        # Use first non-test candidate
        for c in candidates:
            if "test" not in c.name.lower():
                found = c
                break

    if not found:
        raise FileNotFoundError(
            f"Build completed but no executable binary was found. Candidates inspected: {candidates}"
        )

    target_bin = SD_DIR / "sd"
    shutil.copy(str(found), str(target_bin))
    target_bin.chmod(
        target_bin.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR | stat.S_IXUSR
    )

    print(
        f"\n🎉 Successfully installed stable-diffusion.cpp binary ({found.name} -> sd) at:\n   {target_bin.resolve()}"
    )


if __name__ == "__main__":
    setup_sd_cpp()
