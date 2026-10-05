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
| 2.4. Deploy через self-hosted runner | [Зелёный deploy](https://github.com/AnnAnsas/MLPro/actions/runs/37356634689/job/111921020313), [скрин deploy](images/hw3/deploy_success.png), [Runner name](images/hw3/deploy_runner_name.png), [Settings → Runners](images/hw3/runner_settings.png), [история запусков](images/hw3/workflow_runs.png) | `ci #40`, `main`, ручной запуск. Deploy — **38 с**, runner `sem3-kind`, метки `self-hosted, kind`. Smoke прошёл через Ingress. |
| 2.5. Версии данных DVC | [Указатель](dataset/sensor_trends.csv.dvc), [push / diff / checkout / pull](artifacts/hw3/dvc.log), [MLflow v1](images/hw3/dvc_v1.png), [MLflow v2](images/hw3/dvc_v2.png) | Две версии в локальном remote. Откат и восстановление в чистом клоне проверены по MD5. Test F1: **0.74157 → 0.72924**. |
| 2.6. Автомасштабирование | [k9s после нагрузки](images/hw3/k9s_hpa.png), [HPA](k8s/hpa.yaml), [события](artifacts/hw3/hpa/describe.txt), [рост и снижение](artifacts/hw3/hpa/observations.log) | **2 → 4 → 2** реплики; оба события `SuccessfulRescale` зафиксированы. После нагрузки — 2 готовых пода; на скрине k9s CPU 9% при цели 60%, границы 2–4. |
| 2.6. 10 пользователей, 60 с | [Замеры](artifacts/hw3/hpa/results.json) | Реплик 2–4; p95 **79 мс**; CPU/под в среднем **214m**, диапазон 66–751m; память 291–395 МиБ; ошибок 0. |
| 2.6. 30 пользователей, 120 с | [Замеры](artifacts/hw3/hpa/results.json) | Реплик 4; p95 **28 мс**; CPU/под в среднем **91m**, диапазон 41–154m; память 292–325 МиБ; ошибок 0. |
| 2.6. 60 пользователей, 240 с | [Замеры](artifacts/hw3/hpa/results.json) | Реплик 4; p95 **34 мс**; CPU/под в среднем **126m**, диапазон 65–183m; память 296–335 МиБ; ошибок 0. |
| 2.7. Три поломки и починки | [Инцидент GitHub Actions](https://www.githubstatus.com/) | Пока не выполнено. 05.10.2026 job `tests` в PR #16 более 15 минут ожидал hosted runner (`ubuntu-latest`). С 22:11 МСК GitHub сообщил о деградации Actions; возможная причина задержки (images/hw3/github_actions_incident.png). |

## Журнал проблем

| Ошибка | Причина / диагностика | Исправление |
|---|---|---|
| `helm: command not found` | Helm не установлен. | `brew install helm`; `helm version` → 4.3.0. |
| `TLS handshake timeout`, `CrashLoopBackOff` системных подов | Из 3916 МиБ доступно около 580 МиБ, используется swap. Давление на память; OOM не подтверждён. | Мониторинг и Airflow остановлены, Docker перезапущен. Все поды восстановились; после возврата Airflow доступно около 1054 МиБ. Мониторинг выключен. |
| После `kubectl scale` поды не останавливались | Controller-manager падал и не применял число реплик. | После перезапуска Docker команды отработали; Prometheus повторно уменьшен до 0 после остановки оператора. |
| `Registered model alias champion not found` | [Первый прогон](http://mlflow.localhost/#/experiments/1/runs/9623d9d340124b2496500ca5f3a02bcd) обращался к ещё отсутствующему алиасу. | Добавлена проверка `get_registered_model().aliases`; следующий запуск завершился успешно. |
| Deploy: поды `Pending`, `Insufficient memory` | Запрошено 3490 МиБ из ~3916; новые поды требовали ещё по 1 ГиБ. `apply` и `set image` создавали два ReplicaSet. | Airflow остановлен. CI применяет Deployment сразу с SHA-образом; `maxSurge=0`, `maxUnavailable=1` ограничивают обновление двумя подами. |
| API: `password authentication failed for user "postgres"` | CI обновил Secret, а пароль уже запущенной БД остался от локальной проверки 2.3. | Пароль роли согласован с Secret через `ALTER ROLE`, данные сохранены. После перезапуска обе реплики готовы. |
| HPA: `FailedGetResourceMetric` при запуске | Для новых подов ещё не было метрик CPU. | После первого сбора HPA получил метрики и увеличил число реплик; ручное исправление не потребовалось. |

## Ответы на вопросы

1. **Почему tests и build в GitHub, а deploy локально?** Тестам и сборке достаточно кода и зависимостей, а облачный runner не видит kind на ноутбуке за NAT. Альтернативы — VPN, туннель или GitOps-агент внутри кластера; self-hosted runner проще для локальной домашки и сам подключается к GitHub.

2. **Зачем runner сеть kind, Docker socket и group-add 0?** Сеть `kind` даёт доступ к узлу и API кластера, Docker socket — возможность загрузить образ в kind через Docker хоста. `--group-add 0` даёт доступ к сокету с группой root; без этих настроек возможны ошибки соединения с кластером или `permission denied` при обращении к Docker.

3. **Зачем dry-run и apply для Secret?** `--dry-run=client -o yaml` формирует манифест, а `apply` создаёт Secret или обновляет существующий. Обычный `create secret` при повторном деплое завершится ошибкой `AlreadyExists`.

4. **Чем challenger отличается от champion?** Challenger — последний кандидат, champion — модель, прошедшая гейт и выбранная для сервиса. Алиас позволяет переключить модель без изменения образа: у нас откат v6 → v4 занял 75.101 с с учётом паузы проверки разрешения; `rollout undo` откатывает шаблон Deployment, но не алиас MLflow.

5. **Что будет без обученной модели?** При заданном `MODEL_NAME` загрузка модели или алиаса завершится ошибкой, сервис не станет готовым. В k9s будут перезапуски и затем `CrashLoopBackOff`, в логах пода — ошибка реестра, в CI — ожидание rollout и таймаут деплоя.

6. **Как запрос доходит до MLflow?** `mlflow.localhost:80` → проброс kind на порт узла `30080` → Traefik → Ingress → Service MLflow:5000 → под:5000. `allowed-hosts` разрешает имена в заголовке Host, CORS — обращения браузера с указанного origin; проброс порта 80 задаётся при создании контейнера узла kind, одним Ingress его добавить нельзя.

7. **Как HPA рассчитал число реплик?** Формула: `ceil(текущие реплики × текущий CPU% / целевой CPU%)`; в замере при двух репликах и 95% CPU получилось `ceil(2 × 95 / 60) = 4`, столько HPA и запросил. При четырёх репликах и 109% формула даёт 8, но наш максимум — 4; снижение задержало стандартное окно стабилизации 300 с, после чего число реплик вернулось к двум.

8. **Где лежат данные и как восстановить версию N?** В Git лежат указатель `.csv.dvc`, настройки и код; CSV хранится в DVC-кэше и remote `../dvc-storage`. Для модели N нужно открыть её run в MLflow, взять `data_md5`, найти коммит с таким MD5 в указателе, восстановить указатель через `git checkout <коммит> -- dataset/sensor_trends.csv.dvc` и выполнить `uv run dvc pull`; MD5 полученного CSV должен совпасть с параметром прогона.

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

Для локальной проверки собран `my-service:hw3-alias`, запущены PostgreSQL и одна реплика API. В ConfigMap кластера заданы `MODEL_NAME=my-service`, `MODEL_ALIAS=champion`, `MLFLOW_TRACKING_URI=http://mlflow.mlops.svc.cluster.local:5000`. В пункте 2.4 эти настройки применяет CI к существующему кластеру `sem3`.

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

После проверки 2.3 Airflow был восстановлен; при выполнении 2.4 снова остановлен для освобождения памяти.


### 2.4. CI/CD в локальный kind

[Workflow](.github/workflows/ci.yml): tests и build выполняются в GitHub, deploy — в Docker-runner `sem3-kind` в сети `kind`. `workflow_dispatch` передаёт имя кластера, по умолчанию `sem3`. Образ — `ghcr.io/annansas/my-service:sha-a97c3d27b0257b12c0fb54672b0b4a75da1c890d`.

Secret применяется через `--dry-run=client -o yaml | kubectl apply -f -`. Smoke идёт на `sem3-control-plane:30080` с `Host: my-service.localhost` и проверяет источник модели в `/health`, класс 1 для растущего сигнала из `example.json` и ровно одну строку в БД с полученным `request_id`.

[GitHub API job](https://api.github.com/repos/AnnAnsas/MLPro/actions/jobs/111921020313) подтвердил `success`, `runner_name: sem3-kind` и успешный шаг smoke. На [скриншоте Set up job](images/hw3/deploy_runner_name.png) видна строка `Runner name: sem3-kind`. Скрин Settings → Actions → Runners показывает `sem3-kind`, Linux, ARM64, kind, статус Idle.

Настройка **Require approval for all external contributors** этими скриншотами не подтверждена. После сдачи runner нужно выключить и удалить регистрацию в Settings → Actions → Runners.


### 2.5. Данные в DVC

Remote — соседняя папка `../dvc-storage`; в `.dvc/config` путь считается от `.dvc`. CSV исключён из Git, указатель содержит MD5 и размер. Для восстановления на другом компьютере нужна копия remote.

- **v1**, коммит `f6527be`: 1800 окон, MD5 `6d54f179e1394a7c600d6485838aceee`. [Прогон](http://mlflow.localhost/#/experiments/2/runs/cc1a01bbe2064aceb0cce6405ad817cb).
- **v2**, коммит `825fc7a`: 1728 окон, MD5 `3b4320a5898d952f1657acd6663d423a`. Удалены 72 train-окна с более чем 5 пропусками среди значений датчиков. Validation и test побайтово сохранены. [Прогон](http://mlflow.localhost/#/experiments/2/runs/b6ecadace32c422ba3ef7f5188919855).

Оба обучения — 8 эпох, seed 42. Очистка снизила test F1 на 0.01233. Прогоны находятся в эксперименте `my-service-dvc`, модели — `my-service-data-v1` и `my-service-data-v2`: гейт не сравнивает версии с разными `data_md5`. Алиас рабочего сервиса сохранён.

Выполненные команды:

```bash
uv add --dev dvc                         # установить DVC
uv run dvc init                         # создать настройки
uv run dvc config core.analytics false  # отключить аналитику
git rm --cached dataset/sensor_trends.csv # убрать CSV только из Git
uv run dvc add dataset/sensor_trends.csv # создать/обновить указатель
uv run dvc remote add -d local ../dvc-storage # назначить хранилище
uv run dvc push                         # сохранить данные; выполнено для v1 и v2
uv run dvc diff HEAD~1                  # показать изменение после коммита v2
```

Проверка отката (с фиксированными коммитами, чтобы команды работали после новых изменений):

```bash
git checkout f6527be -- dataset/sensor_trends.csv.dvc
uv run dvc checkout # восстановить v1
git checkout 825fc7a -- dataset/sensor_trends.csv.dvc
uv run dvc checkout # вернуть v2
```

Обучение выполнено на каждой версии; для второй `v1` заменено на `v2`:

```bash
MLFLOW_TRACKING_URI=http://mlflow.localhost \
MLFLOW_EXPERIMENT=my-service-dvc MODEL_NAME=my-service-data-v1 \
MODEL_OUTPUT=/private/tmp/my-service-dvc-v1.joblib EPOCHS=8 \
uv run python -m my_service.train
```

В соседнем чистом клоне CSV и DVC-кэш отсутствовали. `uv run --no-sync dvc pull` восстановил **3 799 453 байта**, MD5 совпал с v2. Использовалось готовое Python-окружение проекта; данные загружены из remote.

Dockerfile не копирует датасет. Тесты используют свои фикстуры: **20 passed**, 2 интеграционных теста без БД исключены. `ruff check .` — без ошибок.


### 2.6. HPA

Установлен metrics-server chart `3.14.0`. HPA: CPU **60%** от request `100m`, минимум **2**, максимум **4** реплики. Максимум ограничен памятью Docker (~3.8 ГиБ). CI применяет `k8s/hpa.yaml` вместе с Ingress; `replicas: 2` в Deployment не менялось.

До изменения под нагрузкой: **322–376 МиБ/под**, request **1Gi**. Новый request — **512Mi** (376 МиБ + запас ~36%); CPU request **100m**, limits **1 CPU / 1Gi** сохранены.

Использован существующий `tests/load_testing/locustfile.py`: `/v1/predict` и `/health` в соотношении 5:1, пауза 1–2 с. Три прогона последовательно, без сброса числа реплик между ними; p95 относится ко всем запросам. Поэтому первый прогон включает масштабирование, остальные используют уже готовые реплики.

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm upgrade --install metrics-server metrics-server/metrics-server \
  --version 3.14.0 -n kube-system -f platform/metrics-server-values.yaml --wait
kubectl top nodes # проверить доступность метрик
kubectl top pods -l app=my_service # измерить CPU и память
kubectl set resources deployment my-service --requests=cpu=100m,memory=512Mi
kubectl rollout status deployment/my-service --timeout=120s
kubectl apply -f k8s/hpa.yaml # включить автомасштабирование
```

Нагрузка через Ingress (пары пользователей/длительности: `10/60s`, `30/120s`, `60/240s`):

```bash
uv run --no-sync locust -f tests/load_testing/locustfile.py --headless \
  -u 60 -r 20 -t 240s --host http://my-service.localhost --csv /private/tmp/hpa-run60
kubectl get hpa -w # наблюдать число реплик
kubectl describe hpa my-service # проверить события SuccessfulRescale
```

Фактические замеры HPA и `kubectl top pods` записаны каждые 20 с в [журнал](artifacts/hw3/hpa/observations.log).

Результат: **2 → 4 → 2**, события `SuccessfulRescale` сохранены. После остановки нагрузки HPA снизил целевое число реплик в 22:19:00 (МСК); в 22:19:34 подтверждены 2 текущие и 2 желаемые реплики. Память после проверки — **311–321 МиБ/под**, узел — **2385 МиБ (60%)**. Пиковый замер при запуске новых подов — 395 МиБ; request 512Mi даёт около 30% запаса.
