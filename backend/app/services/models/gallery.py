import json
import logging
import platform
from pathlib import Path
from typing import Any

import yaml
from huggingface_hub import hf_hub_download, snapshot_download
from sqlmodel import Session, select

from app.core.config import settings
from app.database.engine import engine
from app.database.models import ModelConfig, Task
from app.services.tasks.queue import register_task_handler

logger = logging.getLogger(__name__)


class ModelGalleryService:
    def __init__(self):
        self.presets_dir = settings.BASE_DIR / "data" / "models" / "presets"
        self.presets_dir.mkdir(parents=True, exist_ok=True)

    def load_presets(self) -> list[dict[str, Any]]:
        """Loads YAML presets and enriches them with OS compatibility & install status."""
        presets = []
        current_os = platform.system().lower()
        is_apple_silicon = current_os == "darwin" and platform.machine() == "arm64"

        if not self.presets_dir.exists():
            return presets

        with Session(engine) as db:
            registered_paths = {m.file_path for m in db.exec(select(ModelConfig)).all()}

        for yaml_file in sorted(self.presets_dir.glob("*.yaml")):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not data or "id" not in data:
                        continue

                    allowed_platforms = [
                        p.lower() for p in data.get("platforms", ["linux", "windows", "darwin"])
                    ]
                    is_compatible = current_os in allowed_platforms
                    if data.get("format") == "mlx" and not is_apple_silicon:
                        is_compatible = False

                    expected_path = (settings.MODELS_DIR / data["filename"]).resolve()
                    is_installed = str(expected_path) in registered_paths or expected_path.exists()

                    data["compatible"] = is_compatible
                    data["installed"] = is_installed
                    presets.append(data)
            except Exception as e:
                logger.error(f"Failed parsing preset {yaml_file.name}: {e}")

        return presets

    def get_preset(self, preset_id: str) -> dict[str, Any] | None:
        for p in self.load_presets():
            if p["id"] == preset_id:
                return p
        return None

    def install_preset(self, preset: dict[str, Any]) -> Path:
        """Downloads and auto-configures a preset from HuggingFace based on its YAML spec."""
        fmt = preset.get("format", "gguf")
        repo_id = preset["repo_id"]
        filename = preset["filename"]

        if fmt == "mlx":
            dest_dir = settings.MODELS_DIR / filename
            logger.info(f"⬇️ Snapshot downloading MLX bundle '{repo_id}' to {dest_dir}...")
            snapshot_download(
                repo_id=repo_id,
                local_dir=str(dest_dir),
            )
            final_model_path = dest_dir.resolve()
            mmproj_path = None
        else:
            logger.info(f"⬇️ Downloading GGUF '{filename}' from '{repo_id}'...")
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(settings.MODELS_DIR),
            )
            final_model_path = Path(downloaded).resolve()

            mmproj_path = None
            if preset.get("mmproj_filename"):
                logger.info(f"⬇️ Downloading vision projector '{preset['mmproj_filename']}'...")
                proj = hf_hub_download(
                    repo_id=repo_id,
                    filename=preset["mmproj_filename"],
                    local_dir=str(settings.MODELS_DIR),
                )
                mmproj_path = str(Path(proj).resolve())

        # Auto-register with exact YAML specs
        with Session(engine) as db:
            existing = db.exec(
                select(ModelConfig).where(ModelConfig.file_path == str(final_model_path))
            ).first()
            if not existing:
                cfg = ModelConfig(
                    display_name=preset["name"],
                    file_path=str(final_model_path),
                    format=fmt,
                    context_length=preset.get("context_length", 4096),
                    vision_supported=preset.get("vision_supported", False),
                    mmproj_path=mmproj_path,
                    gpu_layers=-1,
                    is_default=False,
                )
                db.add(cfg)
                db.commit()
                logger.info(f"✅ Preset '{preset['name']}' installed and configured.")

        return final_model_path


model_gallery = ModelGalleryService()


@register_task_handler("gallery_preset_install")
async def handle_gallery_install(task: Task, db: Session) -> dict[str, Any]:
    params = json.loads(task.parameters)
    preset_id = params["preset_id"]
    preset = model_gallery.get_preset(preset_id)
    if not preset:
        raise ValueError(f"Preset '{preset_id}' not found.")

    installed_path = model_gallery.install_preset(preset)
    return {"preset_id": preset_id, "path": str(installed_path), "status": "installed"}
