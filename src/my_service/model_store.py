from my_service.config import settings
from my_service.model_loader import load_model as load_file_model


def load_model() -> tuple[object, dict, str]:
    """MODEL_NAME задан — реестр по алиасу; иначе локальный бандл для CI."""
    if not settings.model_name:
        bundle = load_file_model(settings.model_path)
        return bundle["pipeline"], bundle["metadata"], bundle["metadata"]["model_version"]

    import mlflow
    import mlflow.sklearn
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    version = MlflowClient().get_model_version_by_alias(settings.model_name, settings.model_alias)
    pipeline = mlflow.sklearn.load_model(f"models:/{settings.model_name}/{version.version}")
    metadata = mlflow.artifacts.load_dict(f"runs:/{version.run_id}/metadata.json")
    return pipeline, metadata, f"{settings.model_name}-v{version.version}"
