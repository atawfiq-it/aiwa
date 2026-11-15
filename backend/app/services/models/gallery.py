import logging
from typing import Any

import yaml

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelGalleryService:
    def __init__(self):
        self.presets_dir = settings.BASE_DIR / "data" / "models" / "presets"
        self.presets_dir.mkdir(parents=True, exist_ok=True)

    def load_presets(self) -> list[dict[str, Any]]:
        """Loads all declarative YAML model presets from data/models/presets/."""
        presets = []
        if not self.presets_dir.exists():
            return presets

        for yaml_file in self.presets_dir.glob("*.yaml"):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and "id" in data:
                        presets.append(data)
            except Exception as e:
                logger.error(f"Failed parsing preset {yaml_file.name}: {e}")

        return presets


model_gallery = ModelGalleryService()
