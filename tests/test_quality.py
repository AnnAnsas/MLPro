from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

from my_service.model_loader import load_model


def test_model_quality():
    root = Path(__file__).resolve().parents[1]
    bundle = load_model(root / "artifacts/tiny_sequence_transformer_v1.joblib")
    with np.load(root / "tests/data/model_quality.npz") as data:
        predictions = bundle["pipeline"].predict(data["X"])
        f1 = f1_score(data["y"], predictions)

    min_f1 = 1.01  # Намеренно завышенный порог для красного прогона CI.
    assert f1 >= min_f1, f"F1={f1:.4f}, требуется >= {min_f1:.4f}"
