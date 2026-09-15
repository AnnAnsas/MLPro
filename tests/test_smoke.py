from uuid import UUID

import pytest

from my_service.service.app import Features


def test_predict_smoke(client, good_row):
    response = client.post("/v1/predict", json=good_row)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"request_id", "model_version", "prediction", "score", "latency_ms"}
    assert UUID(body["request_id"]).version == 4
    assert 0.0 <= body["score"] <= 1.0
    assert type(body["prediction"]) is int
    assert body["prediction"] in (0, 1)
    assert body["latency_ms"] >= 0
    assert body["model_version"] == client.app.state.version

    sample = Features(**good_row).to_model_input()
    pipeline = client.app.state.pipeline
    assert body["score"] == pytest.approx(float(pipeline.predict_proba(sample)[0, 1]))
    assert body["prediction"] == int(pipeline.predict(sample)[0])


def test_predict_handles_missing_sensor_value(client, good_row):
    good_row["sequence"][0][1] = None
    response = client.post("/v1/predict", json=good_row)
    assert response.status_code == 200
    assert 0.0 <= response.json()["score"] <= 1.0


def test_repeated_predictions_agree(client, good_row):
    first = client.post("/v1/predict", json=good_row)
    second = client.post("/v1/predict", json=good_row)
    assert first.status_code == second.status_code == 200
    first, second = first.json(), second.json()
    assert first["score"] == pytest.approx(second["score"], abs=1e-12, rel=0)
    assert first["prediction"] == second["prediction"]
    assert first["request_id"] != second["request_id"]
