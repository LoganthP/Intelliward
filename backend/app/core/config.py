from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _abs(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    database_url: str = "sqlite:///../data/intelliward.db"
    jwt_secret: str = "change-me-intelliward-jwt-secret"
    jwt_expire_minutes: int = 720
    internal_token: str = "change-me-worker-token"
    embedding_key: str = ""
    anchor_dir: str = "../data/anchors"
    data_dir: str = "../data"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    audit_batch_size: int = 25
    audit_batch_max_age_seconds: int = 60
    background_interval_seconds: float = 2.0
    run_background: bool = True

    @property
    def data_path(self) -> Path:
        p = _abs(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def anchor_path(self) -> Path:
        p = _abs(self.anchor_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        url = self.database_url
        prefix = "sqlite:///"
        if url.startswith(prefix) and ":memory:" not in url:
            rest = url[len(prefix):]
            if not Path(rest).is_absolute() and not rest.startswith("/"):
                f = _abs(rest)
                f.parent.mkdir(parents=True, exist_ok=True)
                return prefix + f.as_posix()
        return url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
