"""Tiny Transformer из ноутбука: обучение, MLflow и гейт по validation F1.

MLFLOW_TRACKING_URI=http://mlflow.localhost EPOCHS=7 uv run python -m my_service.train
"""
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import torch
from mlflow import MlflowClient
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.pipeline import Pipeline

from my_service.generate_dataset import DATA_PATH, FEATURES, SEQ_LEN
from my_service.model import SequencePreprocessor, TinyTransformerClassifier


def load_and_validate(path):
    df = pd.read_csv(path)
    required = {"sequence_id", "step", "target", "split", *FEATURES}
    if missing := required - set(df.columns):
        raise ValueError(f"Нет колонок: {sorted(missing)}")
    if df.empty or df[["sequence_id", "step", "target", "split"]].isna().any().any():
        raise ValueError("Пустой датасет или пропущенные идентификаторы/метки")
    if not set(df["split"]) <= {"train", "validation", "test"}:
        raise ValueError("Неизвестное разбиение")
    if not set(df["target"]) <= {0, 1}:
        raise ValueError("Метки должны быть 0 или 1")
    arrays = {name: ([], []) for name in ("train", "validation", "test")}
    for _, group in df.groupby("sequence_id", sort=True):
        group = group.sort_values("step")
        if (len(group) != SEQ_LEN or not np.array_equal(group["step"], np.arange(SEQ_LEN))
                or group["target"].nunique() != 1 or group["split"].nunique() != 1):
            raise ValueError("Окно должно иметь шаги 0..47, одну метку и одно разбиение")
        x = group[FEATURES].to_numpy(dtype=np.float32)
        if np.isinf(x).any():
            raise ValueError("Бесконечности в данных")
        xs, ys = arrays[group["split"].iloc[0]]
        xs.append(x)
        ys.append(int(group["target"].iloc[0]))
    result = {}
    for name, (xs, ys) in arrays.items():
        if set(ys) != {0, 1}:
            raise ValueError(f"В {name} нужны оба класса")
        result[name] = np.stack(xs), np.asarray(ys)
    return result


def select_threshold(y, probabilities):
    grid = np.linspace(0.1, 0.9, 33)
    scores = np.array([f1_score(y, probabilities >= t, zero_division=0) for t in grid])
    candidates = np.flatnonzero(np.isclose(scores, scores.max()))
    best = candidates[np.argmin(np.abs(grid[candidates] - 0.5))]
    return float(grid[best]), float(scores[best])


def champion_score(client, name, data_md5):
    registered = client.get_registered_model(name)
    if "champion" not in registered.aliases:
        return None, None
    version = client.get_model_version_by_alias(name, "champion")
    run = client.get_run(version.run_id)
    if run.data.params.get("data_md5") != data_md5:
        raise ValueError("Champion обучен на других данных: нужен общий набор для сравнения")
    score = run.data.metrics.get("validation_f1")
    if score is None:
        raise ValueError("У champion нет validation_f1")
    return version.version, score


def main():
    path = Path(os.getenv("DATA_PATH", str(DATA_PATH)))
    model_name = os.getenv("MODEL_NAME", "my-service")
    seed = int(os.getenv("SEED", "42"))
    epochs = int(os.getenv("EPOCHS", "8"))
    min_gain = float(os.getenv("GATE_MIN_GAIN", "0.01"))
    if not np.isfinite(min_gain) or min_gain < 0:
        raise ValueError("GATE_MIN_GAIN должен быть конечным и неотрицательным")
    data_md5 = hashlib.md5(path.read_bytes()).hexdigest()
    data = load_and_validate(path)
    x_train, y_train = data["train"]
    x_val, y_val = data["validation"]
    x_test, y_test = data["test"]
    torch.set_num_threads(2)
    pipeline = Pipeline([
        ("preprocessing", SequencePreprocessor()),
        ("model", TinyTransformerClassifier(epochs=epochs, random_state=seed,
                                            lr=float(os.getenv("LR", "0.002")))),
    ])
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.localhost"))
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "my-service"))
    client = MlflowClient()
    with mlflow.start_run(run_name=f"my-service-epochs-{epochs}") as run:
        mlflow.log_params({"model": "TinyTransformerClassifier", "epochs": epochs,
                           "seed": seed, "data": str(path), "data_md5": data_md5,
                           "gate_metric": "validation_f1", "min_gain": min_gain,
                           **pipeline.named_steps["model"].get_params()})
        pipeline.fit(x_train, y_train)
        threshold, val_f1 = select_threshold(y_val, pipeline.predict_proba(x_val)[:, 1])
        pipeline.set_params(model__threshold=threshold)
        probabilities = pipeline.predict_proba(x_test)[:, 1]
        predicted = pipeline.predict(x_test)
        metrics = {"f1": float(f1_score(y_test, predicted)),
                   "accuracy": float(accuracy_score(y_test, predicted)),
                   "roc_auc": float(roc_auc_score(y_test, probabilities))}
        metadata = {
            "model_version": f"my-service-{run.info.run_id[:8]}",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "task": "binary_sequence_classification",
            "target": "positive_latent_trend_in_sensor_level",
            "features": FEATURES, "input_shape": [None, SEQ_LEN, len(FEATURES)],
            "sequence_length": SEQ_LEN, "input_dtype": "float32", "classes": [0, 1],
            "threshold": threshold, "threshold_selection": "maximum validation F1",
            "data_md5": data_md5, "test_metrics": metrics, "validation_f1": val_f1,
            "dataset": {"path": str(path), "n_train": len(y_train),
                        "n_val": len(y_val), "n_test": len(y_test)},
            "model_params": pipeline.named_steps["model"].get_params(),
            "limitations": ["synthetic data", "fixed-length windows",
                            "uncalibrated probabilities"],
        }
        mlflow.log_metrics({**metrics, "validation_f1": val_f1, "threshold": threshold})
        mlflow.log_dict(metadata, "metadata.json")
        matrix = confusion_matrix(y_test, predicted, labels=[0, 1]).tolist()
        mlflow.log_dict({"labels": [0, 1], "rows": "true", "columns": "predicted",
                         "matrix": matrix}, "confusion_matrix.json")
        mlflow.log_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="260">'
            '<rect width="400" height="260" fill="white"/>'
            '<g font-family="sans-serif" font-size="18" fill="black">'
            '<text x="20" y="30">Test confusion matrix</text>'
            '<text x="20" y="65">Rows: true; columns: predicted</text>'
            f'<text x="30" y="120">TN: {matrix[0][0]}    FP: {matrix[0][1]}</text>'
            f'<text x="30" y="175">FN: {matrix[1][0]}    TP: {matrix[1][1]}</text>'
            '</g></svg>', "confusion_matrix.svg")
        # Собственные sklearn-классы содержат torch-модель; сохраняем через cloudpickle.
        info = mlflow.sklearn.log_model(
            pipeline, name="model", registered_model_name=model_name,
            serialization_format="cloudpickle", code_paths=["src/my_service"],
        )
        version = info.registered_model_version
        client.set_registered_model_alias(model_name, "challenger", version)
        old_version, old_score = champion_score(client, model_name, data_md5)
        promoted = old_score is None or val_f1 > old_score + min_gain
        if promoted:
            client.set_registered_model_alias(model_name, "champion", version)
        mlflow.set_tags({"promoted": str(promoted).lower(), "registry_version": str(version)})
        output = Path(os.getenv("MODEL_OUTPUT", "artifacts/tiny_sequence_transformer_v2.joblib"))
        output.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": pipeline, "metadata": metadata}, output, compress=3)
        output.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2))
        restored = joblib.load(output)["pipeline"]
        np.testing.assert_allclose(restored.predict_proba(x_test[:8]),
                                   pipeline.predict_proba(x_test[:8]), atol=1e-7)
        result = {"run_id": run.info.run_id, "version": version, **metrics,
                  "validation_f1": val_f1, "threshold": threshold,
                  "champion_before": old_version, "champion_f1_before": old_score,
                  "promoted": promoted, "epochs": epochs, "min_gain": min_gain,
                  "aliases_after": client.get_registered_model(model_name).aliases,
                  "data_md5": data_md5}
        mlflow.log_dict(result, "result.json")
    print(json.dumps(result, ensure_ascii=False))
    xcom = Path("/airflow/xcom")
    if xcom.is_dir():
        (xcom / "return.json").write_text(json.dumps(result))
    return result


if __name__ == "__main__":
    main()
