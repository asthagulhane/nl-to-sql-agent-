from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str
    db_path: str = "sample.db"
    max_retries: int = 3
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k_tables: int = 3
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()