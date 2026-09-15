from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from my_service.config import settings
from my_service.service.app import app


@pytest.fixture(scope="session")
def client():
    model_path = Path(__file__).resolve().parents[1] / "artifacts/tiny_sequence_transformer_v1.joblib"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "database_url", None)
        patch.setattr(settings, "model_path", str(model_path))
        with TestClient(app) as client:
            yield client


@pytest.fixture()
def good_row():
    return {"sequence": [[step / 100, 0.2, 0.01] for step in range(48)]}
