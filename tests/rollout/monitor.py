import json
import time
from urllib.request import urlopen

for _ in range(300):
    result = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        with urlopen("http://my-service/health", timeout=2) as response:
            result["status"] = response.status
        with urlopen("http://my-service/openapi.json", timeout=2) as response:
            result["batch"] = "/v1/predict/batch" in json.load(response)["paths"]
    except Exception as error:
        result["error"] = str(error)
    print(json.dumps(result), flush=True)
    time.sleep(0.5)
