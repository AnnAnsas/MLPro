import os

import psycopg
import pytest

DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="нужен Postgres: задайте DATABASE_URL"),
]


def test_prediction_is_logged(client, good_row):
    response = client.post("/v1/predict", json=good_row)
    assert response.status_code == 200, response.text
    body = response.json()

    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            "SELECT model_version, score, features, latency_ms "
            "FROM predictions WHERE request_id = %s",
            (body["request_id"],),
        ).fetchone()
        conn.execute("DELETE FROM predictions WHERE request_id = %s", (body["request_id"],))

    assert row is not None
    assert row[0] == body["model_version"]
    assert row[1] == pytest.approx(body["score"])
    assert row[2] == good_row
    assert row[3] == pytest.approx(body["latency_ms"])
