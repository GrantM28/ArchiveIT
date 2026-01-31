from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARCHIVEIT_", extra="ignore")

    data_dir: str = "/data"
    db_path: str = "/data/archiveit.db"

    redis_url: str = "redis://redis:6379/0"
    queue_name: str = "archiveit"

    # Safety / ops
    max_jobs_per_minute: int = 30
    allow_delete: bool = True

settings = Settings()
