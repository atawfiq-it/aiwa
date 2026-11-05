import argparse
import os
from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
COMFY_DIR = REPO_ROOT / "services" / "comfyui"
COMFY_APP = COMFY_DIR / "app"
COMFY_VENV = COMFY_DIR / ".venv"


def setup_comfyui(checkpoints_dir: str = ""):
    COMFY_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clone ComfyUI repository if needed
    if not (COMFY_APP / "main.py").exists():
        print("📦 Cloning ComfyUI into services/comfyui/app...")
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/comfyanonymous/ComfyUI.git",
                str(COMFY_APP),
            ],
            check=True,
        )
    else:
        print("✅ ComfyUI source code already present.")

    # 2. Create isolated uv virtual environment
    if not COMFY_VENV.exists():
        print("🐍 Creating isolated Python virtual environment for ComfyUI...")
        subprocess.run(["uv", "venv", str(COMFY_VENV)], check=True)

    python_bin = COMFY_VENV / "bin" / "python"

    # Set generous HTTP timeout for large wheel downloads
    env = os.environ.copy()
    env["UV_HTTP_TIMEOUT"] = "300"

    # 3. Install PyTorch directly from official PyTorch CloudFront CDN
    print(
        "⚡ Installing PyTorch directly from Official PyTorch CDN (https://download.pytorch.org/whl/cu124)..."
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_bin),
            "torch",
            "torchvision",
            "torchaudio",
            "--index-url",
            "https://download.pytorch.org/whl/cu124",
        ],
        env=env,
        check=True,
    )

    # 4. Install ComfyUI requirements
    print("📋 Installing ComfyUI dependencies...")
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
        env=env,
        check=True,
    )

    # 5. Link existing model checkpoints
    target_models = COMFY_APP / "models" / "checkpoints"
    target_models.mkdir(parents=True, exist_ok=True)

    if checkpoints_dir:
        src_path = Path(checkpoints_dir).resolve()
        if src_path.exists():
            print(f"🔗 Linking existing checkpoints from {src_path}...")
            count = 0
            for ext in ("*.safetensors", "*.ckpt"):
                for f in src_path.glob(ext):
                    symlink_dest = target_models / f.name
                    if not symlink_dest.exists():
                        symlink_dest.symlink_to(f)
                        print(f"   -> Linked {f.name}")
                        count += 1
            print(f"✅ Linked {count} checkpoint(s).")
        else:
            print(f"⚠️ Checkpoint directory not found at: {src_path}")

    print("\n🎉 ComfyUI successfully provisioned and ready for embedded launch!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install and setup embedded ComfyUI")
    parser.add_argument(
        "--checkpoints",
        default="",
        help="Path to your existing folder containing .safetensors",
    )
    args = parser.parse_args()
    setup_comfyui(args.checkpoints)
