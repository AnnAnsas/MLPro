# Домашняя работа 3

## Отчёт

| Пункт | Подтверждение | Результат |
|---|---|---|
| 2.1. Платформа | [Поды и Ingress](images/hw3/get_pods_ingress.png), [MLflow](images/hw3/mlflow.png), [манифест](platform/mlflow.yaml) | Кластер `sem3`, порт 80 → Traefik:30080. Поды готовы, MLflow открыт в Model training. Allowed hosts, CORS и отключение GenAI-воркеров заданы. |
| 2.2. Модель и гейт | [После второго запуска](images/hw3/aliases_after_second.png), [после третьего](images/hw3/aliases_after_third.png), [решения гейта](artifacts/hw3/three_runs.json) | Tiny Transformer из ноутбука. В MLflow сохранены параметры, метрики, `data_md5`, `metadata.json`, матрица ошибок JSON/SVG. |
| 2.2. Запуск 1: 7 эпох, v4 | [Прогон](http://mlflow.localhost/#/experiments/1/runs/df2c6a87957b40f0bf8f7660a787bb5b), [лог](artifacts/hw3/train_epochs_7.log) | Validation F1 **0.77848**, test F1 **0.71895**. Получила champion и challenger. |
| 2.2. Запуск 2: 1 эпоха, v5 | [Прогон](http://mlflow.localhost/#/experiments/1/runs/f9c9ba57a71149c6b947d38e00cb6fe5), [лог](artifacts/hw3/train_epochs_1.log) | Validation F1 **0.66667**, test F1 **0.66667**. Только challenger; champion остался v4. |
| 2.2. Запуск 3: 8 эпох, v6 | [Прогон](http://mlflow.localhost/#/experiments/1/runs/06a24a5c6be64c43a2ad505717492b62), [лог](artifacts/hw3/train_epochs_8.log) | Validation F1 **0.83045**, test F1 **0.74157**. Забрала champion: 0.83045 > 0.77848 + 0.01. |
| 2.3. Загрузка по алиасу и откат | [Лог проверки](artifacts/hw3/rollback.log), [champion в UI](images/hw3/rollback_alias.png) | `/health`: `my-service-v6` → `my-service-v4`. **75.101 с** от подтверждения в UI до первого ответа v4, включая паузу проверки разрешения. Образ не менялся. |


## Журнал проблем

| Ошибка | Причина / диагностика | Исправление |
|---|---|---|
| `helm: command not found` | Helm не установлен. | `brew install helm`; `helm version` → 4.3.0. |
| `TLS handshake timeout`, `CrashLoopBackOff` системных подов | Из 3916 МиБ доступно около 580 МиБ, используется swap. Давление на память; OOM не подтверждён. | Мониторинг и Airflow остановлены, Docker перезапущен. Все поды восстановились; после возврата Airflow доступно около 1054 МиБ. Мониторинг выключен. |
| После `kubectl scale` поды не останавливались | Controller-manager падал и не применял число реплик. | После перезапуска Docker команды отработали; Prometheus повторно уменьшен до 0 после остановки оператора. |
| `Registered model alias champion not found` | [Первый прогон](http://mlflow.localhost/#/experiments/1/runs/9623d9d340124b2496500ca5f3a02bcd) обращался к ещё отсутствующему алиасу. | Добавлена проверка `get_registered_model().aliases`; следующий запуск завершился успешно. |
| Deploy: поды `Pending`, `Insufficient memory` | Запрошено 3490 МиБ из ~3916; новые поды требовали ещё по 1 ГиБ. `apply` и `set image` создавали два ReplicaSet. | Airflow остановлен. CI применяет Deployment сразу с SHA-образом; `maxSurge=0`, `maxUnavailable=1` ограничивают обновление двумя подами. |
| API: `password authentication failed for user "postgres"` | CI обновил Secret, а пароль уже запущенной БД остался от локальной проверки 2.3. | Пароль роли согласован с Secret через `ALTER ROLE`, данные сохранены. После перезапуска обе реплики готовы. |

## Команды из терминала

### Подготовка

| Команда | Что делает |
|---|---|
| `source /Users/sabel/Documents/MLPro/.venv/bin/activate` | Активирует Python-окружение проекта в текущем терминале. |
| `brew install helm` | Устанавливает Helm через Homebrew. |
| `helm version` | Показывает версию Helm. |
| `helm repo add prometheus-community https://prometheus-community.github.io/helm-charts` | Добавляет источник чартов мониторинга. |
| `helm repo add traefik https://traefik.github.io/charts` | Добавляет источник чартов Traefik. |
| `helm repo update` | Обновляет локальные индексы чартов. |
| `kind get clusters` | Показывает локальные kind-кластеры; были `mlpro` и `mlpro-hw1`. |
| `kind delete cluster --name mlpro` | Удаляет старый кластер `mlpro`. |
| `kind delete cluster --name mlpro-hw1` | Удаляет старый кластер `mlpro-hw1`. |

### Кластер и приложения

Создание кластера с пробросом порта из конфигурации; текущий контекст переключается на `kind-sem3`:

```bash
kind create cluster --name sem3 --config platform/kind-config.yaml
```

Загрузка локальных Docker-образов в узел kind:

```bash
kind load docker-image apache/airflow:3.3.2 ghcr.io/mlflow/mlflow:v3.16.1 --name sem3
```

Создание или обновление ресурсов MLflow и Airflow по манифестам:

```bash
kubectl apply -f platform/mlflow.yaml
kubectl apply -f platform/airflow.yaml
```

Установка мониторинга с настройками проекта и ожиданием до 15 минут:

```bash
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --version 91.5.2 -n monitoring --create-namespace \
  -f platform/monitoring-values.yaml --wait --timeout 15m
```

Установка Traefik с настройками из проекта:

```bash
helm upgrade --install traefik traefik/traefik \
  --version 41.6.0 -n traefik --create-namespace \
  -f platform/traefik-values.yaml --wait
```

Создание маршрутов по именам хостов:

```bash
kubectl apply -f platform/ingress.yaml
```

### Проверки и остановка сервисов

| Команда | Что делает |
|---|---|
| `kubectl get ingress -A` | Показывает Ingress во всех namespace. |
| `kubectl get pods -A` | Показывает готовность, состояние и перезапуски всех подов. |
| `kubectl get pods,ingress -A` | Выводит поды и Ingress для подтверждения пункта 2.1. |
| `k9s` | Открывает терминальный интерфейс Kubernetes. |
| `k9s -n mlops` | Открывает k9s в namespace `mlops`. |
| `kubectl scale deployment airflow -n mlops --replicas=0` | Останавливает Airflow, сохраняя Deployment и PVC. |
| `kubectl scale deployment --all -n monitoring --replicas=0` | Останавливает Deployment мониторинга, включая Grafana и оператор Prometheus. |
| `kubectl scale statefulset --all -n monitoring --replicas=0` | Останавливает StatefulSet Prometheus; PVC не удаляется этой командой. |

### Обучение: три запуска

`EPOCHS` задаёт число эпох. Команды выполнены последовательно:

```bash
MLFLOW_TRACKING_URI=http://mlflow.localhost EPOCHS=7 uv run python -m my_service.train
MLFLOW_TRACKING_URI=http://mlflow.localhost EPOCHS=1 uv run python -m my_service.train
MLFLOW_TRACKING_URI=http://mlflow.localhost EPOCHS=8 uv run python -m my_service.train
```

Повтор при существующем champion v6 не повторит исходный сценарий: кандидаты будут сравниваться с ним.


### 2.3. Сервис и откат

`model_store.load_model()` получает версию по `MODEL_NAME` / `MODEL_ALIAS` и загружает модель и metadata из одного прогона. Без `MODEL_NAME` используется локальный бандл; 20 тестов без MLflow прошли. `/health` показывает загруженную версию и источник модели.

Для локальной проверки собран `my-service:hw3-alias`, запущены PostgreSQL и одна реплика API. В ConfigMap кластера заданы `MODEL_NAME=my-service`, `MODEL_ALIAS=champion`, `MLFLOW_TRACKING_URI=http://mlflow.mlops.svc.cluster.local:5000`. Эти локальные настройки не внесены в общий ConfigMap: текущий CI ещё создаёт кластер без MLflow (пункт 2.4 впереди).

Локальные настройки применены к ConfigMap кластера (не к файлу):

```bash
kubectl patch configmap my-service-config --type merge -p '{"data":{"MODEL_NAME":"my-service","MODEL_ALIAS":"champion","MLFLOW_TRACKING_URI":"http://mlflow.mlops.svc.cluster.local:5000"}}'
```

В **Model registry → my-service → Version 4 → Add aliases** выбран `champion`, затем подтверждён **Save aliases** клавишей Enter. Это предыдущий champion; v5 гейт не прошла. После смены алиаса выполнено:

```bash
kubectl rollout restart deploy/my-service
kubectl rollout status deploy/my-service --timeout=120s
curl --fail --silent http://my-service.localhost/health
```

До: `{"status":"ok","model_version":"my-service-v6","model_path":"models:/my-service@champion"}`.

После: `{"status":"ok","model_version":"my-service-v4","model_path":"models:/my-service@champion"}`.

Замер — **75.101 с**, опрос `/health` каждые 0.5 с. Перезапуск задержала автоматическая проверка разрешения; после команды «продолжи» он завершился. Это полное время эксперимента, не чистое время старта пода. ImageID до и после одинаковый: `sha256:540c6b93c5eff918a9c2b0ac70ec9376403e1918bd3124a09858b5872e25dcc4`. Предсказание вернуло v4, в БД найдена одна строка с его request_id.

Airflow временно останавливался на время сборки и развёртывания, затем восстановлен. Итог: API, PostgreSQL, Airflow, MLflow и системные поды — `1/1 Running`.
