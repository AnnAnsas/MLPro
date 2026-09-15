import time
import uuid
from typing import Literal

import numpy as np
from fastapi import FastAPI, BackgroundTasks, HTTPException

from pydantic import BaseModel, Field, FiniteFloat

from my_service.config import settings
from my_service.model_loader import load_model
from my_service import db

from contextlib import asynccontextmanager


SensorValue = FiniteFloat | None


class Features(BaseModel):
    sequence: list[tuple[SensorValue, SensorValue, SensorValue]] = Field(
        min_length=48,
        max_length=48,
        description="[sensor_level, sensor_aux, sensor_noise]; null — empty value",
    )

    def to_model_input(self) -> np.ndarray:
        return np.asarray([self.sequence], dtype=np.float32)


class Prediction(BaseModel):
    request_id: uuid.UUID
    model_version: str
    prediction: Literal[0, 1]
    score: FiniteFloat = Field(ge=0, le=1, description="Probability of class 1")
    latency_ms: FiniteFloat = Field(ge=0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = load_model(settings.model_path)
    app.state.pipeline = bundle["pipeline"]
    app.state.meta = bundle["metadata"]
    app.state.version = bundle["metadata"]["model_version"]

    if settings.database_url:
        db.init()
    yield
    app.state.pipeline = None


app = FastAPI(title="MLPro_my_service", version="0.1.0", lifespan=lifespan)

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_version": getattr(app.state, "version", None)}

@app.get("/ready")
def ready() -> dict:
    if not getattr(app.state, "pipeline", None):
        raise HTTPException(status_code=503, detail="Model is not loaded")

    return {"status": "ready", "model_version": app.state.version}


@app.post("/v1/predict")
def predict(x: Features, bg: BackgroundTasks) -> Prediction:
    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())
    payload = x.model_dump()
    score = float(app.state.pipeline.predict_proba(x.to_model_input())[0, 1])

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    if settings.database_url:
        bg.add_task(db.save_prediction, request_id, payload, score, app.state.version, latency_ms)

    return Prediction(
        request_id=request_id,
        model_version=app.state.version,
        prediction=int(score >= app.state.meta["threshold"]),
        score=score,
        latency_ms=latency_ms,
    )
