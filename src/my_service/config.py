from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_path: str = "artifacts/tiny_sequence_transformer_v1.joblib"
    model_name: str | None = None
    model_alias: str = "champion"
    mlflow_tracking_uri: str = "http://mlflow.localhost"
    database_url: str | None = None

    model_config = {"env_file": ".env"}

settings = Settings()
