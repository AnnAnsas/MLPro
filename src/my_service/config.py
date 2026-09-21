from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_path: str = "artifacts/tiny_sequence_transformer_v1.joblib"
    database_url: str | None = None
    log_level: str = "INFO"

    model_config = {"env_file": ".env"}

settings = Settings()  