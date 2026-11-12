import argparse
from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
COMFY_DIR = REPO_ROOT / "services" / "comfyui"
COMFY_APP = COMFY_DIR / "app"
COMFY_VENV = COMFY_DIR / ".venv"


def setup_comfyui(checkpoints_dir: str = ""):
    COMFY_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clone stable ComfyUI release tag v0.3.10
    if not (COMFY_APP / "main.py").exists():
        print("📦 Cloning stable ComfyUI (tag v0.3.10) into services/comfyui/app...")
        subprocess.run(
            [
                "git",
                "clone",
                "--branch",
                "v0.3.10",
                "--single-branch",
                "https://github.com/comfyanonymous/ComfyUI.git",
                str(COMFY_APP),
            ],
            check=True,
        )
    else:
        print("✅ ComfyUI source code present.")

    # 2. Create isolated uv environment
    if not COMFY_VENV.exists():
        print("🐍 Creating isolated Python virtual environment for ComfyUI...")
        subprocess.run(["uv", "venv", str(COMFY_VENV)], check=True)

    python_bin = COMFY_VENV / "bin" / "python"

    # 3. Upgrade PyTorch to 2.5.1 (Fixes list[int] infer_schema ValueError)
    print("⚡ Installing PyTorch 2.5.1 with CUDA 12.4 support...")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_bin),
            "torch>=2.5.1",
            "torchvision",
            "torchaudio",
            "--index-url",
            "https://download.pytorch.org/whl/cu124",
        ],
        check=True,
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_bin),
            "-r",
            str(COMFY_APP / "requirements.txt"),
        ],
        check=True,
    )

    # 4. Link existing model checkpoints
    target_models = COMFY_APP / "models" / "checkpoints"
    target_models.mkdir(parents=True, exist_ok=True)

    if checkpoints_dir:
        src_path = Path(checkpoints_dir).resolve()
        if src_path.exists():
            print(f"🔗 Linking existing checkpoints from {src_path}...")
            for ext in ["*.safetensors", "*.ckpt"]:
                for f in src_path.glob(ext):
                    symlink_dest = target_models / f.name
                    if not symlink_dest.exists():
                        symlink_dest.symlink_to(f)
                        print(f"   -> Linked {f.name}")
        else:
            print(f"⚠️ Checkpoint directory not found at: {src_path}")

    print("\n🎉 ComfyUI fixed, upgraded to PyTorch 2.5.1, and ready!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install and setup embedded ComfyUI")
    parser.add_argument(
        "--checkpoints",
        default="",
        help="Path to your existing folder containing .safetensors",
    )
    args = parser.parse_args()
    setup_comfyui(args.checkpoints)
