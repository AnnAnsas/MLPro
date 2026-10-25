"""Воспроизвести версию датасета, на которую указывает DVC-файл."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

from my_service.generate_dataset import FEATURES, generate

EXPECTED_MD5 = "3b4320a5898d952f1657acd6663d423a"
EXPECTED_REMOVED_WINDOWS = 72
MAX_MISSING_VALUES = 5


def file_md5(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "md5").hexdigest()


def bootstrap(path: Path) -> str:
    generate(path=path)
    frame = pd.read_csv(path)

    train = frame.loc[frame["split"].eq("train")]
    missing_by_sequence = (
        train[FEATURES]
        .isna()
        .groupby(train["sequence_id"])
        .sum()
        .sum(axis=1)
    )
    removed_ids = missing_by_sequence.loc[
        missing_by_sequence > MAX_MISSING_VALUES
    ].index

    if len(removed_ids) != EXPECTED_REMOVED_WINDOWS:
        raise RuntimeError(
            f"ожидалось {EXPECTED_REMOVED_WINDOWS} удалённых окон, "
            f"получено {len(removed_ids)}"
        )

    frame = frame.loc[~frame["sequence_id"].isin(removed_ids)]
    frame.to_csv(path, index=False, float_format="%.7g")

    digest = file_md5(path)
    if digest != EXPECTED_MD5:
        raise RuntimeError(f"ожидался MD5 {EXPECTED_MD5}, получен {digest}")

    print(
        f"{path}: удалено {len(removed_ids)} train-окон, "
        f"строк {len(frame)}, md5 {digest}"
    )
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dataset/sensor_trends.csv"),
    )
    args = parser.parse_args()
    bootstrap(args.output)


if __name__ == "__main__":
    main()
