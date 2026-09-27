import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from pydantic import BaseModel, Field, FiniteFloat

from my_service import db
from my_service.config import settings
from my_service.model_loader import load_model

SensorValue = FiniteFloat | None


class Features(BaseModel):
    model_config = {"extra": "forbid"}

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


@app.middleware("http")
async def log_prediction_request(request: Request, call_next):
    if request.method != "POST" or request.url.path not in {
        "/v1/predict",
        "/v1/predict/batch",
    }:
        return await call_next(request)

    started = time.perf_counter()
    request.state.request_id = str(uuid.uuid4())
    request.state.scores = None

    payload = {}
    if settings.database_url:
        try:
            payload = await request.json()
        except ValueError:
            pass

    try:
        response = await call_next(request)
    except Exception:
        logging.exception("Prediction failed")
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )

    if settings.database_url:
        scores = request.state.scores if response.status_code == 200 else None
        response.background = BackgroundTask(
            db.save_prediction,
            request_id=request.state.request_id,
            features=payload,
            score=(
                scores[0]
                if scores is not None and request.url.path == "/v1/predict"
                else None
            ),
            model_version=app.state.version,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            status_code=response.status_code,
            scores=scores,
        )

    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_version": getattr(app.state, "version", None)}

@app.get("/ready")
def ready() -> dict:
    if not getattr(app.state, "pipeline", None):
        raise HTTPException(status_code=503, detail="Model is not loaded")

    return {"status": "ready", "model_version": app.state.version}


@app.post("/v1/predict")
def predict(x: Features, request: Request) -> Prediction:
    t0 = time.perf_counter()
    request_id = request.state.request_id
    score = float(app.state.pipeline.predict_proba(x.to_model_input())[0, 1])
    request.state.scores = [score]

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return Prediction(
        request_id=request_id,
        model_version=app.state.version,
        prediction=int(score >= app.state.meta["threshold"]),
        score=score,
        latency_ms=latency_ms,
    )


class BatchFeatures(BaseModel):
    model_config = {"extra": "forbid"}

    rows: list[Features] = Field(min_length=1, max_length=1000)


class BatchResult(BaseModel):
    prediction: Literal[0, 1]
    score: FiniteFloat = Field(ge=0, le=1)


class BatchPrediction(BaseModel):
    request_id: uuid.UUID
    model_version: str
    predictions: list[BatchResult]
    latency_ms: FiniteFloat = Field(ge=0)


@app.post("/v1/predict/batch")
def predict_batch(batch: BatchFeatures, request: Request) -> BatchPrediction:
    t0 = time.perf_counter()
    request_id = request.state.request_id
    inputs = np.asarray([row.sequence for row in batch.rows], dtype=np.float32)
    scores = app.state.pipeline.predict_proba(inputs)[:, 1]
    predictions = [
        BatchResult(prediction=int(score >= app.state.meta["threshold"]), score=float(score))
        for score in scores
    ]
    request.state.scores = [item.score for item in predictions]
    return BatchPrediction(
        request_id=request_id,
        model_version=app.state.version,
        predictions=predictions,
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
