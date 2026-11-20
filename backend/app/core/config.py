import platform
import re
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Root directory of the repository
if getattr(sys, "frozen", False):
    # When running as a packaged desktop app, use writable ~/.aiwa directory
    ROOT_DIR = Path.home() / ".aiwa"
    ROOT_DIR.mkdir(parents=True, exist_ok=True)
else:
    # Development repository root
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment & API Configuration
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Local Multimodal AI Workstation"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    # Paths (Resolved relative to repo root)
    BASE_DIR: Path = ROOT_DIR
    DATA_DIR: Path = ROOT_DIR / "data"
    DATABASE_DIR: Path = ROOT_DIR / "data" / "database"
    DATABASE_URL: str = ""
    MODELS_DIR: Path = ROOT_DIR / "data" / "models"
    UPLOADS_DIR: Path = ROOT_DIR / "data" / "uploads"
    GENERATED_DIR: Path = ROOT_DIR / "data" / "generated"

    # Security & Auth
    AUTH_ENABLED: bool = True
    TOKEN_FILE_PATH: Path = ROOT_DIR / "data" / ".aiwa_session_token"

    # Hardware & VRAM Arbiter
    AIWA_HARDWARE_ACCELERATION: str = "auto"
    MAX_GPU_USAGE_PERCENT: float = 80.0
    DEFAULT_STATIC_VRAM_GB: float = 8.0
    VRAM_SAFETY_MARGIN_MB: int = 1024

    # Model Discovery & Defaults
    DIFFUSION_MODEL_DIRECTORIES: str = ""
    LLM_MODEL_DIRECTORIES: str = ""
    DEFAULT_LLM_MODEL: str = "Qwen2.5-VL-7B-Instruct"
    DEFAULT_DIFFUSION_MODEL: str = "sd_xl_turbo"

    # LLM / llama.cpp defaults
    LLAMA_SERVER_BIN: str = ""
    LLAMA_SERVER_HOST: str = "127.0.0.1"
    LLAMA_SERVER_PORT: int = 8080
    LLAMA_PARALLEL_SLOTS: int = 1
    MODEL_IDLE_TTL_SECONDS: int = 600

    # External Services & Tasks
    COMFYUI_PORT: int = 8188
    COMFYUI_BASE_URL: str = ""
    TASK_WORKER_POLL_INTERVAL_SECONDS: float = 1.0

    @property
    def HOST(self) -> str:
        return self.API_HOST

    @property
    def PORT(self) -> int:
        return self.API_PORT

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def model_post_init(self, __context) -> None:
        self.DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        if not self.COMFYUI_BASE_URL:
            object.__setattr__(
                self, "COMFYUI_BASE_URL", f"http://{self.API_HOST}:{self.COMFYUI_PORT}"
            )

        if not self.DATABASE_URL:
            db_path = self.DATABASE_DIR / "aiwa.db"
            object.__setattr__(self, "DATABASE_URL", f"sqlite:///{db_path}")

        if not self.LLAMA_SERVER_BIN:
            bin_name = "llama-server.exe" if platform.system() == "Windows" else "llama-server"
            local_bin = self.BASE_DIR / "services" / "llama-cpp" / bin_name
            if local_bin.exists():
                object.__setattr__(self, "LLAMA_SERVER_BIN", str(local_bin.resolve()))
            else:
                object.__setattr__(self, "LLAMA_SERVER_BIN", bin_name)

    def get_diffusion_search_paths(self) -> list[Path]:
        """Strictly scans DIFFUSION_MODEL_DIRECTORIES from .env. Falls back to data/models if unset."""
        paths: list[Path] = []

        if self.DIFFUSION_MODEL_DIRECTORIES:
            raw_entries = re.split(r"[,;\n]", self.DIFFUSION_MODEL_DIRECTORIES)
            for entry in raw_entries:
                cleaned = entry.strip().strip("'\"")
                if cleaned:
                    p = Path(cleaned).resolve()
                    if p.exists() and p.is_dir() and p not in paths:
                        paths.append(p)

        if not paths:
            paths.append(self.MODELS_DIR.resolve())

        return paths

    def get_llm_search_paths(self) -> list[Path]:
        """Parses multiple LLM directories from .env and includes data/models."""
        paths: list[Path] = [self.MODELS_DIR.resolve()]

        if self.LLM_MODEL_DIRECTORIES:
            raw_entries = re.split(r"[,;\n]", self.LLM_MODEL_DIRECTORIES)
            for entry in raw_entries:
                cleaned = entry.strip().strip("'\"")
                if cleaned:
                    p = Path(cleaned).resolve()
                    if p.exists() and p.is_dir() and p not in paths:
                        paths.append(p)

        return paths


settings = Settings()
