from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings loaded from Environment or Defaults."""

    APP_TITLE: str = "Bulk Certificate Generator"
    DATABASE_URL: str = "sqlite:///./bulk_certificates.db"
    STORAGE_DIR: str = "./storage"
    MAX_RECIPIENTS: int = 5000
    BASE_URL: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
