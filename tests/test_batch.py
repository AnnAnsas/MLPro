from unittest.mock import patch

import pytest


def test_batch_matches_single_and_calls_model_once(client, good_row):
    other = {"sequence": [[-step / 100, None, 0.1] for step in range(48)]}
    rows = [good_row, other]
    expected = [client.post('/v1/predict', json=row).json() for row in rows]
    pipeline = client.app.state.pipeline
    with patch.object(pipeline, 'predict_proba', wraps=pipeline.predict_proba) as predict:
        response = client.post('/v1/predict/batch', json={'rows': rows})
        assert response.status_code == 200
        predict.assert_called_once()
        assert predict.call_args.args[0].shape == (2, 48, 3)
    body = response.json()
    assert body['latency_ms'] >= 0
    assert body['model_version'] == client.app.state.version
    assert len(body['predictions']) == 2
    for actual, single in zip(body['predictions'], expected, strict=True):
        assert actual['score'] == pytest.approx(single['score'], abs=1e-6)
        assert actual['prediction'] == single['prediction']


@pytest.mark.parametrize('size', [0, 1001])
def test_batch_limits(client, good_row, size):
    assert client.post('/v1/predict/batch', json={'rows': [good_row] * size}).status_code == 422


@pytest.mark.parametrize('size', [1, 1000])
def test_batch_valid_sizes(client, good_row, size):
    response = client.post('/v1/predict/batch', json={'rows': [good_row] * size})
    assert response.status_code == 200
    assert len(response.json()['predictions']) == size
