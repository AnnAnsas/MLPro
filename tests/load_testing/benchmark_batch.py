import json
import sys
from pathlib import Path
from statistics import median
from urllib.request import Request, urlopen

URL = "http://127.0.0.1:8000/v1/predict/batch"
ROW = {"sequence": [[step / 100, 0.2, 0.01] for step in range(48)]}


def measure(size):
    request = Request(
        URL,
        data=json.dumps({"rows": [ROW] * size}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=120) as response:
        body = json.load(response)
    assert len(body["predictions"]) == size
    return body["latency_ms"]


def main():
    for size in (1, 500):
        measure(size)
    samples = {1: [], 500: []}
    for _ in range(10):
        for size in samples:
            samples[size].append(measure(size))
    medians = {size: median(values) for size, values in samples.items()}
    result = {
        "url": URL,
        "warmup_requests_per_size": 1,
        "samples_ms": samples,
        "median_ms": medians,
        "ratio": medians[500] / medians[1],
    }
    if "--stdout-only" not in sys.argv:
        path = Path(__file__).parent / "results/batch_benchmark.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
