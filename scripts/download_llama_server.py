from pathlib import Path
import shutil
import stat
import zipfile
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "services" / "llama-cpp"
TARGET_DIR.mkdir(parents=True, exist_ok=True)


def download_llama_server():
    print("🔍 Fetching latest CUDA release from ggerganov/llama.cpp...")
    api_url = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        res = client.get(api_url)
        if res.status_code != 200:
            raise RuntimeError(f"Failed to fetch release info: {res.text}")

        assets = res.json().get("assets", [])
        # Look for Ubuntu/Linux x64 with CUDA 12
        selected_asset = None
        for a in assets:
            name = a["name"].lower()
            if (
                "ubuntu" in name
                and "cuda" in name
                and "x64" in name
                and name.endswith(".zip")
            ):
                selected_asset = a
                break

        # Fallback to standard Ubuntu x64 binary if CUDA-specific asset is not named standard
        if not selected_asset:
            for a in assets:
                name = a["name"].lower()
                if "bin-ubuntu-x64.zip" in name:
                    selected_asset = a
                    break

        if not selected_asset:
            raise RuntimeError(
                "Could not find suitable Linux prebuilt binary in release."
            )

        asset_url = selected_asset["browser_download_url"]
        asset_name = selected_asset["name"]
        print(f"⬇️  Downloading {asset_name} (~150MB)...")

        zip_dest = TARGET_DIR / asset_name
        with client.stream("GET", asset_url) as stream:
            with open(zip_dest, "wb") as f:
                for chunk in stream.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

        print("📦 Extracting binary files...")
        with zipfile.ZipFile(zip_dest, "r") as zip_ref:
            zip_ref.extractall(TARGET_DIR)

        # Cleanup zip
        zip_dest.unlink()

        # Find and chmod +x the server executable
        server_bin = TARGET_DIR / "llama-server"
        if not server_bin.exists():
            # Sometimes placed inside a build/bin subdirectory
            found = list(TARGET_DIR.glob("**/llama-server"))
            if found:
                shutil.move(str(found[0]), str(server_bin))

        if server_bin.exists():
            server_bin.chmod(server_bin.stat().st_mode | stat.S_IEXEC)
            print(f"✅ llama-server successfully installed at: {server_bin.resolve()}")
        else:
            raise FileNotFoundError(
                "Extraction succeeded but 'llama-server' binary not found."
            )


if __name__ == "__main__":
    download_llama_server()
