"""Проверка DVC-датасета и запись результата в MLflow.

MLFLOW_TRACKING_URI=http://mlflow.localhost uv run python -m my_service.validate_data
"""

import hashlib
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow
import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

from my_service.generate_dataset import DATA_PATH, FEATURES, SEQ_LEN

ROW_SCHEMA = pa.DataFrameSchema(
    {
        "sequence_id": Column(int, Check.ge(0)),
        "step": Column(int, Check.in_range(0, SEQ_LEN - 1)),
        "sensor_level": Column(float, Check.in_range(-6.0, 6.0), nullable=True),
        "sensor_aux": Column(float, Check.in_range(-3.0, 3.0), nullable=True),
        "sensor_noise": Column(float, Check.in_range(-6.0, 6.0), nullable=True),
        "target": Column(int, Check.isin([0, 1])),
        "split": Column(str, Check.isin(["train", "validation", "test"])),
    },
    unique=["sequence_id", "step"],
    strict=True,
)


def _complete_windows(df: pd.DataFrame) -> bool:
    sizes = df.groupby("sequence_id", sort=False).size()
    return bool(sizes.eq(SEQ_LEN).all())


def _balanced_target(df: pd.DataFrame) -> bool:
    share = float(df["target"].mean())
    return 0.45 <= share <= 0.55


def _stable_level_median(df: pd.DataFrame) -> bool:
    return abs(float(df["sensor_level"].median())) <= 0.25


def _limited_missing_values(df: pd.DataFrame) -> bool:
    return bool(df[FEATURES].isna().mean().le(0.03).all())


DATASET_SCHEMA = pa.DataFrameSchema(
    checks=[
        Check(lambda df: len(df) >= 80_000, name="at_least_80000_rows"),
        Check(_complete_windows, name="48_rows_per_sequence"),
        Check(_balanced_target, name="positive_share_045_055"),
        Check(_stable_level_median, name="sensor_level_median_abs_le_025"),
        Check(_limited_missing_values, name="feature_missing_share_le_003"),
    ],
)


def validate_rows(df: pd.DataFrame) -> pd.DataFrame:
    return ROW_SCHEMA.validate(df, lazy=True)


def validate_dataset(df: pd.DataFrame) -> pd.DataFrame:
    return DATASET_SCHEMA.validate(df, lazy=True)


def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    return validate_dataset(validate_rows(df))


def run_validation(path: Path) -> dict[str, object]:
    data_md5 = hashlib.md5(path.read_bytes()).hexdigest()
    df = pd.read_csv(path)
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.localhost"))
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "my-service"))

    with mlflow.start_run(run_name="validate-data") as run:
        mlflow.log_params({"data": str(path), "data_md5": data_md5, "rows": len(df)})
        try:
            validate_dataframe(df)
        except pa.errors.SchemaErrors as error:
            mlflow.set_tag("valid", "false")
            with TemporaryDirectory() as directory:
                failure_path = Path(directory) / "failure_cases.csv"
                error.failure_cases.to_csv(failure_path, index=False)
                mlflow.log_artifact(failure_path)
            raise

        mlflow.set_tag("valid", "true")
        result = {"run_id": run.info.run_id, "valid": True, "rows": len(df),
                  "data_md5": data_md5}
        mlflow.log_dict(result, "validation.json")
        return result


def main() -> None:
    path = Path(os.getenv("DATA_PATH", str(DATA_PATH)))
    try:
        result = run_validation(path)
    except (OSError, pd.errors.ParserError, pa.errors.SchemaErrors) as error:
        print(f"Данные не прошли проверку: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(result)


if __name__ == "__main__":
    main()
