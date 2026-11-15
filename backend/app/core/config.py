import re
from dataclasses import Field
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Root directory of the repository
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"  # "development" | "production"

    # API Configuration
    PROJECT_NAME: str = "Local Multimodal AI Workstation"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

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

    # LLM / llama.cpp defaults
    LLAMA_CPP_BASE_URL: str = "http://127.0.0.1:8080"
    MODEL_IDLE_TTL_SECONDS: int = 600  # 10 minutes default
    LLAMA_SERVER_BIN: str = "llama-server"  # system binary or path to llama-server
    LLAMA_SERVER_HOST: str = "127.0.0.1"
    LLAMA_SERVER_PORT: int = 8080
    LLAMA_PARALLEL_SLOTS: int = 1
    DEFAULT_STATIC_VRAM_GB: float = 8.0  # Fallback VRAM budget when pynvml is unavailable
    COMFYUI_BASE_URL: str = Field(
        default_factory=lambda: f"http://127.0.0.1:{settings.COMFYUI_PORT}"
    )

    TASK_WORKER_POLL_INTERVAL_SECONDS: float = 1.0
    LLAMA_SERVER_BIN: str = ""
    DIFFUSION_MODEL_DIRECTORIES: str = ""  # Comma or colon-separated paths in .env

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    AIWA_HARDWARE_ACCELERATION: str = "auto"  # "auto", "cuda", "rocm", "metal", "vulkan", "cpu"
    MAX_GPU_USAGE_PERCENT: float = 80.0
    VRAM_SAFETY_MARGIN_MB: int = 1024

    LLM_MODEL_DIRECTORIES: str = ""

    COMFYUI_PORT: int = 8188

    DEFAULT_LLM_MODEL: str = "Qwen3-VL-8B-Instruct"
    DEFAULT_DIFFUSION_MODEL: str = "dreamshaper 8"

    def get_llm_search_paths(self) -> list[Path]:
        """Parses multiple LLM directories from .env and includes data/models."""
        paths: list[Path] = [self.MODELS_DIR.resolve()]

        if self.LLM_MODEL_DIRECTORIES:
            raw_entries = re.split(r"[,:\n]", self.LLM_MODEL_DIRECTORIES)
            for entry in raw_entries:
                cleaned = entry.strip().strip("'\"")
                if cleaned:
                    p = Path(cleaned).resolve()
                    if p.exists() and p.is_dir() and p not in paths:
                        paths.append(p)

        return paths

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def model_post_init(self, __context) -> None:
        # Existing directory creations...
        self.DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        # Auto-detect local prebuilt binary if LLAMA_SERVER_BIN is unset
        if not self.LLAMA_SERVER_BIN:
            local_bin = self.BASE_DIR / "services" / "llama-cpp" / "llama-server"
            if local_bin.exists():
                object.__setattr__(self, "LLAMA_SERVER_BIN", str(local_bin.resolve()))
            else:
                object.__setattr__(self, "LLAMA_SERVER_BIN", "llama-server")

        if not self.DATABASE_URL:
            db_path = self.DATABASE_DIR / "aiwa.db"
            object.__setattr__(self, "DATABASE_URL", f"sqlite:///{db_path}")

    def get_diffusion_search_paths(self) -> list[Path]:
        """Parses multiple diffusion directories from .env and includes data/models."""
        paths: list[Path] = [self.MODELS_DIR.resolve()]

        if self.DIFFUSION_MODEL_DIRECTORIES:
            # Split on commas, colons, or newlines
            raw_entries = re.split(r"[,:\n]", self.DIFFUSION_MODEL_DIRECTORIES)
            for entry in raw_entries:
                cleaned = entry.strip().strip("'\"")
                if cleaned:
                    p = Path(cleaned).resolve()
                    if p.exists() and p.is_dir() and p not in paths:
                        paths.append(p)

        return paths


settings = Settings()
