import pytest


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model_version": client.app.state.version,
    }


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "model_version": client.app.state.version,
    }


def test_not_ready(client, monkeypatch):
    monkeypatch.setattr(client.app.state, "pipeline", None)
    assert client.get("/ready").status_code == 503


@pytest.mark.parametrize("length", [0, 47, 49])
def test_invalid_sequence_length_is_422(client, length):
    response = client.post("/v1/predict", json={"sequence": [[0.1, 0.2, 0.3]] * length})
    assert response.status_code == 422


@pytest.mark.parametrize("step", [[0.1, 0.2], [0.1, 0.2, 0.3, 0.4], ["invalid", 0.2, 0.3]])
def test_invalid_step_is_422(client, good_row, step):
    good_row["sequence"][0] = step
    assert client.post("/v1/predict", json=good_row).status_code == 422


def test_missing_sequence_is_422(client):
    assert client.post("/v1/predict", json={}).status_code == 422
