#!/usr/bin/env bash
# Поднимает локальную платформу: kind, MLflow, Airflow, RustFS/S3,
# Traefik, Prometheus и Grafana. Повторный запуск безопасен.
set -euo pipefail

CLUSTER=${CLUSTER:-sem4}
S3_KEY=${S3_KEY:-dvcadmin}
S3_SECRET=${S3_SECRET:-dvc-secret-123}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

for command in docker kind kubectl helm curl; do
  command -v "$command" >/dev/null || {
    echo "Не найдена команда: $command" >&2
    exit 1
  }
done
docker info >/dev/null 2>&1 || {
  echo "Docker Desktop не запущен" >&2
  exit 1
}

echo "== kind: $CLUSTER"
if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER" --config platform/kind-config.yaml
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo "== MLflow, S3 и Airflow"
kubectl apply -f platform/mlflow.yaml
kubectl -n mlops create secret generic s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID="$S3_KEY" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f platform/s3.yaml -f platform/airflow.yaml

echo "== Traefik, Prometheus и Grafana"
helm repo add traefik https://traefik.github.io/charts >/dev/null 2>&1 || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm upgrade --install traefik traefik/traefik --version 41.6.0 \
  -n traefik --create-namespace -f platform/traefik-values.yaml \
  --wait --timeout 15m
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --version 91.5.2 -n monitoring --create-namespace \
  -f platform/monitoring-values.yaml --wait --timeout 15m
kubectl apply -f platform/ingress.yaml

echo "== ожидание платформы"
kubectl -n mlops rollout status deploy/mlflow --timeout=15m
kubectl -n mlops rollout status deploy/rustfs --timeout=15m
kubectl -n mlops rollout status deploy/airflow --timeout=15m
kubectl -n monitoring rollout status deploy/monitoring-grafana --timeout=15m
kubectl -n monitoring rollout status \
  statefulset/prometheus-monitoring-kube-prometheus-prometheus --timeout=15m

echo "== бакет dvc"
bucket_ready=false
for _ in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT \
    --aws-sigv4 "aws:amz:us-east-1:s3" \
    --user "$S3_KEY:$S3_SECRET" http://s3.localhost/dvc) || code=000
  if [[ "$code" == 200 || "$code" == 409 ]]; then
    bucket_ready=true
    echo "Бакет dvc готов ($code)"
    break
  fi
  sleep 2
done
if [[ "$bucket_ready" != true ]]; then
  echo "Не удалось создать бакет dvc" >&2
  exit 1
fi

kubectl get pods -A
echo
echo "MLflow:    http://mlflow.localhost"
echo "Airflow:   http://airflow.localhost"
echo "Grafana:   http://grafana.localhost (admin/admin)"
echo "S3:        http://s3.localhost"
echo "S3 console:http://s3-console.localhost/rustfs/console/index.html"
