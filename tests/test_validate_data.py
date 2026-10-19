import pandas as pd
import pandera.pandas as pa
import pytest

from my_service.generate_dataset import FEATURES, SEQ_LEN
from my_service.validate_data import validate_dataset, validate_rows


def sample_rows() -> pd.DataFrame:
    rows = []
    for sequence_id, target in ((1, 0), (2, 1)):
        for step in range(SEQ_LEN):
            rows.append(
                {
                    "sequence_id": sequence_id,
                    "step": step,
                    "sensor_level": 0.1,
                    "sensor_aux": -0.2,
                    "sensor_noise": 0.3,
                    "target": target,
                    "split": "train",
                }
            )
    return pd.DataFrame(rows)


def test_good_rows_pass() -> None:
    result = validate_rows(sample_rows())
    assert list(result.columns) == ["sequence_id", "step", *FEATURES, "target", "split"]


def test_out_of_range_sensor_value_is_rejected() -> None:
    data = sample_rows()
    data.loc[0, "sensor_aux"] = 4.0

    with pytest.raises(pa.errors.SchemaErrors):
        validate_rows(data)


def test_small_export_is_rejected() -> None:
    with pytest.raises(pa.errors.SchemaErrors, match="at_least_80000_rows"):
        validate_dataset(sample_rows())
