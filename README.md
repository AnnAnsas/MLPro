# My Service

Сервис определяет положительный скрытый тренд в окне из 48 измерений трёх датчиков. Tiny Transformer возвращает класс, score, версию модели из MLflow и `request_id`; запрос сохраняется в PostgreSQL.

Модель обучается на версионируемом датасете, регистрируется в MLflow и попадает в сервис через алиас `champion`. Локальная Kubernetes-платформа содержит MLflow, Airflow, RustFS/S3, Prometheus, Grafana и Traefik.

Доказательства выполнения, ответы на вопросы и журнал проблем собраны в [`REPORT.md`](REPORT.md).

## Quickstart

Нужны Docker Desktop, Git, `uv`, `kind`, `kubectl`, Helm и свободный порт 80. Для передачи секретов из терминала также нужен GitHub CLI `gh`. Для платформы достаточно 4 ГБ памяти Docker; перед запуском лучше закрыть другие локальные кластеры.

### Windows 11 и WSL2

На Windows проект запускается из Ubuntu в WSL2, а не из PowerShell или Git Bash. В PowerShell с правами администратора установите WSL2:

```powershell
wsl --install -d Ubuntu
```

Для компьютера с 12 ГБ RAM задайте WSL2 верхний предел 8 ГБ и swap 4 ГБ. Создайте файл `%UserProfile%\.wslconfig`:

```ini
[wsl2]
memory=8GB
processors=4
swap=4GB
```

Примените настройки:

```powershell
wsl --shutdown
```

В Docker Desktop включите **Use the WSL 2 based engine** и интеграцию с Ubuntu в **Resources → WSL Integration**. После запуска Docker Desktop откройте терминал Ubuntu и проверьте окружение:

```bash
grep -qi microsoft /proc/version
test "$(uname -m)" = x86_64
docker info >/dev/null
test -S /var/run/docker.sock
free -h
command -v git uv kind kubectl helm curl gh
! ss -ltn | grep -q ':80 '
```

Все следующие команды Quickstart выполняются в этом терминале Ubuntu. Образы публикуются для `linux/amd64` и `linux/arm64`, поэтому Windows-компьютер с процессором x86-64 получит AMD64-вариант. Файлы Bash и YAML закреплены в Git с окончаниями строк LF.

Сначала создайте fork репозитория в GitHub. Укажите URL своего fork без суффикса `.git` и клонируйте его в каталог `MLPro`:

```bash
export REPO_URL='https://github.com/<OWNER>/<REPOSITORY>'
git clone "${REPO_URL}.git" MLPro
cd MLPro

test "$(git remote get-url origin)" = "${REPO_URL}.git"
test -f pyproject.toml
test -f dataset/sensor_trends.csv.dvc
uv sync --frozen
uv run ruff check .
uv run pytest
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

Для нового кластера бакет `dvc` сначала пуст. Настройте локальные ключи, воспроизведите версию данных из `.dvc`-указателя, загрузите её в S3 и проверьте восстановление:

```bash
uv run --no-sync dvc remote modify --local laptop access_key_id dvcadmin
uv run --no-sync dvc remote modify --local laptop secret_access_key dvc-secret-123
uv run --no-sync python scripts/bootstrap_data.py
uv run --no-sync dvc add dataset/sensor_trends.csv
uv run --no-sync dvc push
rm dataset/sensor_trends.csv
uv run --no-sync dvc pull
uv run --no-sync dvc status
```

Скрипт удаляет 72 train-окна, в которых больше пяти пропусков, и завершится с ошибкой, если итоговый MD5 отличается от `3b4320a5898d952f1657acd6663d423a`.

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

Создайте пароль базы и сохраните его в Actions secret своего fork:

```bash
export DB_PASSWORD="$(openssl rand -hex 24)"
printf '%s' "$DB_PASSWORD" | \
  gh secret set DB_PASSWORD --repo "${REPO_URL#https://github.com/}"
```

Проверить наличие секрета можно командой:

```bash
gh secret list --repo "${REPO_URL#https://github.com/}" | grep '^DB_PASSWORD'
```

Без GitHub CLI добавьте `DB_PASSWORD` через **Settings → Secrets and variables → Actions → New repository secret**.

В своём fork откройте **Settings → Actions → Runners → New self-hosted runner** и скопируйте временный токен. Runner запускается в сети kind и получает доступ к Docker socket:

```bash
export RUNNER_TOKEN='<токен из GitHub>'
docker rm -f gh-runner 2>/dev/null || true
docker run -d --name gh-runner --network kind --group-add 0 \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e REPO_URL="$REPO_URL" \
  -e RUNNER_TOKEN="$RUNNER_TOKEN" \
  ghcr.io/actions/actions-runner:2.337.0 \
  bash -lc 'if [ ! -f .runner ]; then ./config.sh --unattended \
    --url "$REPO_URL" --token "$RUNNER_TOKEN" --name sem4-kind \
    --labels kind --replace; fi; exec ./run.sh'
```

Проверьте, что runner работает и подключён к сети кластера:

```bash
docker ps --filter name=gh-runner
docker inspect gh-runner --format '{{json .NetworkSettings.Networks}}'
```

После появления runner со статусом **Idle** в своём fork откройте **Actions → ci → Run workflow**, выберите ветку `main`, укажите `kind_cluster=sem4` и запустите workflow. Multi-arch образ для `linux/amd64` и `linux/arm64` собирается на GitHub runner, поэтому эта сборка почти не расходует память локального Docker. После зелёного deploy выполните контрольные команды:

```bash
kubectl get nodes
kubectl get pods -A
kubectl get ingress -A
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
