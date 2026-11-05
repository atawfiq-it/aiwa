import logging
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download
from sqlmodel import Session

from app.core.config import settings
from app.database.engine import engine
from app.database.models import ModelConfig, Task
from app.services.tasks.queue import register_task_handler

logger = logging.getLogger(__name__)


class HuggingFaceService:
    def __init__(self):
        self.api = HfApi()

    def search_gguf_models(self, query: str = "qwen", limit: int = 15) -> list[dict[str, Any]]:
        """Searches HuggingFace specifically for GGUF repos, tagging vision/mmproj availability."""
        models = self.api.list_models(
            search=query,
            filter="gguf",
            sort="downloads",
            direction=-1,
            limit=limit,
            full=False,
        )

        results = []
        for m in models:
            repo_id = m.id
            is_vision = any(k in repo_id.lower() for k in ["-vl", "vision", "qwen2.5-vl", "llava"])

            results.append(
                {
                    "repo_id": repo_id,
                    "author": repo_id.split("/")[0] if "/" in repo_id else "",
                    "name": repo_id.split("/")[-1] if "/" in repo_id else repo_id,
                    "downloads": getattr(m, "downloads", 0),
                    "likes": getattr(m, "likes", 0),
                    "is_vision": is_vision,
                    "created_at": getattr(m, "created_at", None),
                }
            )
        return results

    def get_repo_files(self, repo_id: str) -> dict[str, Any]:
        """Lists all GGUF files in the repository and checks for mmproj vision projectors."""
        files = self.api.list_repo_files(repo_id=repo_id)
        gguf_files = []
        mmproj_files = []

        for f in files:
            if f.endswith(".gguf"):
                if "mmproj" in f.lower():
                    mmproj_files.append(f)
                else:
                    gguf_files.append(f)

        return {
            "repo_id": repo_id,
            "has_vision": len(mmproj_files) > 0,
            "gguf_files": gguf_files,
            "mmproj_files": mmproj_files,
        }

    def download_and_register(
        self,
        repo_id: str,
        filename: str,
        mmproj_filename: str | None = None,
    ) -> Path:
        """Downloads GGUF model and mmproj using huggingface_hub directly to data/models."""
        dest_dir = settings.MODELS_DIR
        print(f"⬇️ Downloading {filename} from {repo_id}...")

        # Download main GGUF
        model_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(dest_dir),
            local_dir_use_symlinks=False,
        )

        # Download paired mmproj if present
        mmproj_path = None
        if mmproj_filename:
            print(f"⬇️ Downloading vision projector {mmproj_filename}...")
            mmproj_path = hf_hub_download(
                repo_id=repo_id,
                filename=mmproj_filename,
                local_dir=str(dest_dir),
                local_dir_use_symlinks=False,
            )

        # Auto-register into SQLite
        with Session(engine) as db:
            display_name = Path(filename).stem.replace("-Q4_K_M", "").replace("_", " ")
            cfg = ModelConfig(
                display_name=display_name,
                file_path=str(Path(model_path).resolve()),
                mmproj_path=str(Path(mmproj_path).resolve()) if mmproj_path else None,
                vision_supported=mmproj_path is not None,
                context_length=4096,
                gpu_layers=-1,
                is_default=False,
            )
            db.add(cfg)
            db.commit()
            print(f"✅ Auto-registered '{display_name}' into Model Supervisor catalog.")

        return Path(model_path)


hf_service = HuggingFaceService()


@register_task_handler("hf_model_download")
async def handle_hf_download(task: Task, db: Session) -> dict[str, Any]:
    """Background task handler for model downloads."""
    import json

    params = json.loads(task.parameters)
    repo_id = params["repo_id"]
    filename = params["filename"]
    mmproj_filename = params.get("mmproj_filename")

    model_path = hf_service.download_and_register(
        repo_id=repo_id,
        filename=filename,
        mmproj_filename=mmproj_filename,
    )

    return {
        "status": "completed",
        "file_path": str(model_path),
        "filename": filename,
    }
