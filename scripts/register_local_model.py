import argparse
from pathlib import Path
import sys
import httpx

API_BASE = "http://127.0.0.1:8000/api/v1"


def register_model(
    model_path: str,
    mmproj_path: str,
    display_name: str,
    context_length: int,
    token: str,
):
    model_file = Path(model_path).resolve()
    if not model_file.exists():
        print(f"❌ Error: Model path does not exist: {model_file}")
        sys.exit(1)

    # If a directory was provided, auto-detect the .gguf file inside it
    if model_file.is_dir():
        gguf_candidates = list(model_file.glob("*.gguf"))
        if not gguf_candidates:
            print(f"❌ Error: No .gguf files found inside folder: {model_file}")
            sys.exit(1)
        # Select the primary quant
        model_file = gguf_candidates[0]
        print(f"📁 Directory provided. Auto-selected: {model_file.name}")

    mmproj_file = Path(mmproj_path).resolve() if mmproj_path else None
    if mmproj_file and not mmproj_file.exists():
        print(f"❌ Error: Multimodal projector not found at: {mmproj_file}")
        sys.exit(1)

    payload = {
        "display_name": display_name,
        "file_path": str(model_file),
        "format": "gguf",
        "context_length": context_length,
        "vision_supported": mmproj_file is not None,
        "mmproj_path": str(mmproj_file) if mmproj_file else None,
        "gpu_layers": -1,  # Full offload within the 80% budget
        "is_default": True,
    }

    headers = {"X-AIWA-Token": token}

    # timeout 90 seconds
    with httpx.Client(timeout=90.0) as client:
        # Check supervisor status and VRAM first
        vram_res = client.get(f"{API_BASE}/models/status", headers=headers)
        if vram_res.status_code == 200:
            vram = vram_res.json().get("vram", {})
            print(
                f"ℹ️  GPU Budget: {vram.get('allowed_ceiling_mb')} MB "
                f"({vram.get('max_usage_percent')}% cap of {vram.get('total_mb')} MB total)"
            )

        res = client.post(f"{API_BASE}/models", json=payload, headers=headers)
        if res.status_code == 200:
            data = res.json()
            model_id = data["id"]
            print(f"✅ Successfully registered '{display_name}' (ID: {model_id})")

            # Load the model
            print("🚀 Loading model into llama-server via Model Supervisor...")
            load_res = client.post(
                f"{API_BASE}/models/{model_id}/load", headers=headers
            )
            if load_res.status_code == 200:
                print("🎉 Model is loaded and Ready for inference!")
            else:
                print(f"⚠️  Load returned: {load_res.text}")
        else:
            print(f"❌ Failed registering model: {res.text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register local GGUF model in AIWA")
    parser.add_argument("--model", required=True, help="Path to GGUF model file")
    parser.add_argument(
        "--mmproj", default="", help="Path to mmproj GGUF file (for vision)"
    )
    parser.add_argument("--name", default="Qwen3-VL-4B", help="Display name")
    parser.add_argument("--ctx", type=int, default=4096, help="Context length")
    parser.add_argument(
        "--token", default="", help="Session token (reads from file if empty)"
    )

    args = parser.parse_args()

    # Read session token if not explicitly passed
    token = args.token
    if not token:
        token_path = Path("data/.aiwa_session_token")
        if token_path.exists():
            token = token_path.read_text().strip()

    if not token:
        print(
            "❌ Error: No session token found. Start the backend with 'just dev' first."
        )
        sys.exit(1)

    register_model(args.model, args.mmproj, args.name, args.ctx, token)
