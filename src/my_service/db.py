import psycopg
from psycopg.types.json import Json

from my_service.config import settings

DDL = """
CREATE TABLE IF NOT EXISTS predictions (

    request_id      uuid PRIMARY KEY,
    ts      timestamptz NOT NULL DEFAULT now(),
    model_version       text NOT NULL,
    features        jsonb NOT NULL,
    score double precision,
    latency_ms real,
    status_code integer,
    scores jsonb
)
"""

def init() -> None:
    if not settings.database_url:
        return
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(DDL)
        conn.execute(
            "ALTER TABLE predictions "
            "ADD COLUMN IF NOT EXISTS status_code integer"
        )
        conn.execute(
            "ALTER TABLE predictions "
            "ADD COLUMN IF NOT EXISTS scores jsonb"
        )
        conn.execute(
            "ALTER TABLE predictions ALTER COLUMN score DROP NOT NULL"
        )


def save_prediction(
    request_id: str,
    features: dict,
    score: float | None,
    model_version: str,
    latency_ms: float,
    status_code: int,
    scores: list[float] | None = None,
) -> None:
    if not settings.database_url:
        return

    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "INSERT INTO predictions "
            "(request_id, model_version, features, score, latency_ms, "
            "status_code, scores) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                request_id,
                model_version,
                Json(features),
                score,
                latency_ms,
                status_code,
                Json(scores) if scores is not None else None,
            ),
        )
            

    