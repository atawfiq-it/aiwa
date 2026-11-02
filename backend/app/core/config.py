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
    LLAMA_PARALLEL_SLOTS: int = 4
    DEFAULT_STATIC_VRAM_GB: float = 8.0  # Fallback VRAM budget when pynvml is unavailable
    VRAM_SAFETY_MARGIN_MB: int = 1024  # Keep 1GB safety cushion

    def model_post_init(self, __context) -> None:
        # Guarantee local directories exist
        self.DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        # Set default SQLite URL if not provided
        if not self.DATABASE_URL:
            db_path = self.DATABASE_DIR / "aiwa.db"
            object.__setattr__(self, "DATABASE_URL", f"sqlite:///{db_path}")


settings = Settings()
