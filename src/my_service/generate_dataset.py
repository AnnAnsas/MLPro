"""Воспроизводимые синтетические окна с перекрывающимися классами."""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

FEATURES = ["sensor_level", "sensor_aux", "sensor_noise"]
SEQ_LEN = 48
DATA_PATH = Path("dataset/sensor_trends.csv")


def generate(path=DATA_PATH, n=1800, seed=42):
    rng = np.random.default_rng(seed)
    y = np.arange(n) % 2
    rng.shuffle(y)
    t = np.linspace(-1, 1, SEQ_LEN)[None, :]
    phase = rng.uniform(0, 2 * np.pi, (n, 1))
    amplitude = rng.uniform(0.03, 0.65, (n, 1))
    offset = rng.normal(0, 0.8, (n, 1))
    # Метка — направление исходного тренда. Дрейф измерения от метки независим.
    trend = (2 * y[:, None] - 1) * amplitude * t
    drift = rng.normal(0, 0.30, (n, 1)) * t
    level = offset + trend + drift + 0.35 * np.sin(3 * np.pi * t + phase)
    level += rng.normal(0, 0.55, (n, SEQ_LEN))
    aux = np.sin(2 * np.pi * t + phase) + rng.normal(0, 0.35, (n, SEQ_LEN))
    noise = rng.normal(0, 1, (n, SEQ_LEN))
    x = np.stack([level, aux, noise], axis=-1).astype(np.float32)
    x[rng.random(x.shape) < 0.02] = np.nan
    train, hold = train_test_split(np.arange(n), test_size=0.30, stratify=y,
                                   random_state=seed)
    val, test = train_test_split(hold, test_size=0.5, stratify=y[hold], random_state=seed)
    split = np.empty(n, dtype=object)
    split[train], split[val], split[test] = "train", "validation", "test"
    df = pd.DataFrame(x.reshape(-1, len(FEATURES)), columns=FEATURES)
    df.insert(0, "step", np.tile(np.arange(SEQ_LEN), n))
    df.insert(0, "sequence_id", np.repeat(np.arange(n), SEQ_LEN))
    df["target"] = np.repeat(y, SEQ_LEN)
    df["split"] = np.repeat(split, SEQ_LEN)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.7g")
    print(f"{path}: {n} окон, {len(df)} строк")


if __name__ == "__main__":
    generate()
