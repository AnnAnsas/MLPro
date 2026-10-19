"""Генерирует трафик через Ingress для дашборда Grafana."""

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://my-service.localhost")
    parser.add_argument("--rps", type=float, default=5)
    parser.add_argument("--bad", type=float, default=0.0)
    args = parser.parse_args()

    payloads = [load_payload("example.json"), load_payload("example_negative.json")]
    codes: dict[int, int] = {}
    started = time.time()

    while True:
        payload = dict(random.choice(payloads))
        if random.random() < args.bad:
            payload["sequence"] = payload["sequence"][:-1]
        request = urllib.request.Request(
            f"{args.url}/v1/predict",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                code = response.status
        except urllib.error.HTTPError as error:
            code = error.code
        except (urllib.error.URLError, OSError):
            code = 0

        codes[code] = codes.get(code, 0) + 1
        total = sum(codes.values())
        if total % 50 == 0:
            print(f"{total} запросов за {time.time() - started:.0f} с, коды {codes}", flush=True)
        time.sleep(1 / args.rps)


if __name__ == "__main__":
    main()
