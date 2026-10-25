# My Service

Сервис определяет положительный скрытый тренд в окне из 48 измерений трёх датчиков. Tiny Transformer возвращает класс, score, версию модели из MLflow и `request_id`; запрос сохраняется в PostgreSQL.

Модель обучается на версионируемом датасете, регистрируется в MLflow и попадает в сервис через алиас `champion`. Локальная Kubernetes-платформа содержит MLflow, Airflow, RustFS/S3, Prometheus, Grafana и Traefik.

Доказательства выполнения, ответы на вопросы и журнал проблем собраны в [`REPORT.md`](REPORT.md).

## Quickstart

Нужны Docker Desktop, Git, `uv`, `kind`, `kubectl`, Helm и свободный порт 80. Для платформы достаточно 4 ГБ памяти Docker; перед запуском лучше закрыть другие локальные кластеры.

```bash
git clone https://github.com/AnnAnsas/MLPro.git
cd MLPro
uv sync --frozen
bash platform/up.sh
```

Команда создаёт кластер `sem4`, поднимает платформу и бакет `dvc`. Повторный запуск обновляет существующие ресурсы. Другое имя кластера задаётся так:

```bash
CLUSTER=sem4 bash platform/up.sh
```

Проверка платформы:

```bash
kubectl get pods -A
kubectl get ingress -A
curl --fail http://mlflow.localhost/health
```

Настройка локальных ключей DVC, восстановление данных и проверка записи в S3:

```bash
uv run --no-sync dvc remote modify --local laptop access_key_id dvcadmin
uv run --no-sync dvc remote modify --local laptop secret_access_key dvc-secret-123
uv run --no-sync dvc pull
uv run --no-sync dvc push
```

Проверка восстановленного датасета отдельной командой:

```bash
MLFLOW_TRACKING_URI=http://mlflow.localhost \
uv run --no-sync python -m my_service.validate_data
```

Если Python не разрешает `s3.localhost` в `127.0.0.1`, добавьте в `/etc/hosts` строку `127.0.0.1 s3.localhost` или используйте port-forward. Проверка:

```bash
uv run --no-sync python -c "import socket; print(socket.gethostbyname('s3.localhost'))"
```

Первый `champion`:

```bash
MLFLOW_TRACKING_URI=http://mlflow.localhost EPOCHS=8 \
MODEL_OUTPUT=/tmp/my-service-champion.joblib \
uv run --no-sync python -m my_service.train
```

В GitHub откройте **Settings → Actions → Runners → New self-hosted runner** и скопируйте временный токен. Runner запускается в сети kind и получает доступ к Docker socket:

```bash
export RUNNER_TOKEN='<токен из GitHub>'
docker rm -f gh-runner 2>/dev/null || true
docker run -d --name gh-runner --network kind --group-add 0 \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e REPO_URL=https://github.com/AnnAnsas/MLPro \
  -e RUNNER_TOKEN="$RUNNER_TOKEN" \
  ghcr.io/actions/actions-runner:2.337.0 \
  bash -lc 'if [ ! -f .runner ]; then ./config.sh --unattended \
    --url "$REPO_URL" --token "$RUNNER_TOKEN" --name sem4-kind \
    --labels kind --replace; fi; exec ./run.sh'
```

После появления runner со статусом **Idle** откройте **Actions → ci → Run workflow**, выберите ветку `main`, укажите `kind_cluster=sem4` и запустите workflow. После зелёного deploy:

```bash
curl --fail http://my-service.localhost/health
curl --fail -X POST http://my-service.localhost/v1/predict \
  -H 'Content-Type: application/json' -d @example.json
```

## Адреса

| Компонент | Адрес |
|---|---|
| Сервис | `http://my-service.localhost` |
| MLflow | `http://mlflow.localhost` |
| Airflow | `http://airflow.localhost` |
| Grafana | `http://grafana.localhost` (`admin` / `admin`) |
| S3 API | `http://s3.localhost` |
| S3 Console | `http://s3-console.localhost/rustfs/console/index.html` |

## Ручное переобучение

```bash
MLFLOW_TRACKING_URI=http://mlflow.localhost EPOCHS=8 \
MODEL_OUTPUT=/tmp/my-service.joblib \
uv run --no-sync python -m my_service.train
```

В Airflow тот же процесс запускает DAG `my_service_retrain`: данные проверяются,
модель обучается с гейтом и выкатывается только после получения `champion`.

## Метрики

Дашборд **My Service** доступен в Grafana. Трафик для панелей запускается через Ingress:

```bash
uv run --no-sync python scripts/traffic.py \
  --url http://my-service.localhost --rps 5 --bad 0.05
```

Скрипт чередует положительный и отрицательный примеры. Параметр `--bad` задаёт долю
запросов с неправильной длиной окна; они возвращают `422`.
