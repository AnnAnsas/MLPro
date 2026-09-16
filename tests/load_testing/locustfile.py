from locust import HttpUser, between, task


class ModelUser(HttpUser):
    wait_time = between(1, 2)

    @task(5)
    def predict(self):
        payload = {"sequence": [[step / 100, 0.2, 0.01] for step in range(48)]}
        self.client.post("/v1/predict", json=payload, timeout=30)

    @task(1)
    def health(self):
        self.client.get("/health", timeout=30)
