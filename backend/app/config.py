from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        extra="ignore",
    )

    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    # all = API+scheduler (local uvicorn). api / worker split in compose.
    app_role: str = "all"
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'jobcrm.db'}"
    # Empty = in-process MemoryJobStore. Compose worker: redis://redis:6379/0
    redis_url: str = ""
    # Direct Postgres for Alembic. Empty = database_url (sqlite or already-direct).
    database_migrate_url: str = ""
    # Comma-separated. Prod: the public origin (https://jobs.example.com), not localhost.
    allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # urlsafe-base64 32-byte Fernet key. Empty = store Google tokens plaintext (dev only).
    token_fernet_key: str = ""

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allow_origins.split(",") if item.strip()]

    def cookie_secure(self) -> bool:
        # test/dev over http. prod sits behind nginx TLS — Secure must be on
        # even though uvicorn itself sees HTTP from the docker network.
        return self.app_env not in {"dev", "test"}

    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    def runs_scheduler(self) -> bool:
        if self.app_env == "test":
            return False
        return self.app_role in {"all", "worker"}

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"

    scraper_min_delay_sec: float = 1.5
    scraper_max_delay_sec: float = 4.0
    scraper_max_pages: int = 10

    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_parse_interval_minutes: int = 30
    telegram_messages_per_channel: int = 40

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/api/google/callback"
    google_calendar_timezone: str = "Europe/Moscow"


settings = Settings()
