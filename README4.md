# Отчёт по итоговому проекту

## Выполнение задания

| Пункт | Доказательство | Результат |
|---|---|---|
| 1. Платформа одной командой | [`platform/up.sh`](platform/up.sh), [`platform.log`](artifacts/hw4/platform.log), [`kubectl get pods -A`](images/hw4/kubectl_get_pods.png) | Чистый запуск `sem4` занял 3 мин 57 с. Повторный запуск — 39 с. MLflow, Airflow, RustFS, Traefik, Prometheus и Grafana подняты; бакет `dvc` создан. |
| 2. Метрики и дашборд | [`dashboard.yaml`](k8s/monitoring/dashboard.yaml), [`traffic.py`](scripts/traffic.py), [`traffic.log`](artifacts/hw4/traffic.log) | Grafana показала 2 pod с `my-service-v1`, RPS, p50/p95, долю положительного класса и распределение score. Под длительной нагрузкой при доступных Docker 4 ГБ появились `502/503`; снимок приложен к сдаче. |
| 3. Данные в DVC и S3 | [`sensor_trends.csv.dvc`](dataset/sensor_trends.csv.dvc), [конфигурация DVC](.dvc/config), [Dockerfile](Dockerfile), [`.dockerignore`](.dockerignore), [`dvc.log`](artifacts/hw4/dvc.log) | В git находится только указатель. `dvc push` подтвердил данные в бакете `dvc`: 1 объект, 3,6 МиБ. Локальная сборка образа не завершилась из-за нехватки ресурсов; вывод `docker run ... ls` не получен. Снимок бакета приложен к сдаче. |
| 4. Проверка данных | [`validate_data.py`](src/my_service/validate_data.py), [`test_validate_data.py`](tests/test_validate_data.py), [CI run 39305338626](https://github.com/AnnAnsas/MLPro/actions/runs/39305338626), [MLflow run `valid=false`](http://mlflow.localhost/#/experiments/1/runs/2020e3d76906472db15b51ff4358bfc2) | 25 тестов прошли локально. Испорченный `sensor_aux=4.0` дал код 1, тег `valid=false` и артефакт `failure_cases.csv`. В CI тесты и сборка прошли, deploy остановлен по 10-минутному тайм-ауту при загрузке образа в kind. |
| 5. Конвейер переобучения | [`my_service_retrain.py`](dags/my_service_retrain.py), [CI](.github/workflows/ci.yml) | DAG содержит `validate → train → promoted → rollout`; перед первыми двумя задачами выполняется `dvc pull -r cluster`. Три требуемых сценария пока не сняты. |

![Все компоненты платформы в Running](images/hw4/kubectl_get_pods.png)

## Пороги проверки данных

Границы признаков взяты с запасом от наблюдаемых минимумов и максимумов. Доля класса 1 ограничена 45–55%, медиана `sensor_level` — ±0,25, пропуски — 3%: текущие значения равны 49,8%, 0,032 и 1,88% соответственно.

## Журнал проблем

| Проблема | Причина | Исправление |
|---|---|---|
| Grafana перезапускалась во время первого старта | Grafana 13 выполняла долгую миграцию SQLite и не укладывалась в стандартное окно liveness на ноутбуке с 8 ГБ | Зафиксирована Grafana 11.6.8, liveness отложена на 300 с, CPU ограничен `500m` |
| После локального обучения kubelet медленно создавал поды | Docker использовал около 3,1 из 3,8 ГБ, macOS активно работала со swap | Для локального обучения временно остановлены Airflow и мониторинг; после обучения платформа восстановлена. Traefik получил ресурсы и менее строгие probe |
| После длительной работы один CoreDNS временно стал `0/1` | Кластер занял около 2,9 из доступных Docker 3,8 ГБ, health-check не успел ответить | CoreDNS перезапущен; для освобождения памяти после проверки кластер останавливается |
| Под трафиком сервис и Grafana потеряли готовность | Две реплики модели, Prometheus, Grafana, MLflow и RustFS вместе превысили доступные Docker 4 ГБ | За 271 с генератор получил 128 ответов `200`, 6 ответов `422`, затем 3 сетевые ошибки, 66 ответов `502` и 47 ответов `503`. Исправление не выполнялось; ограничение честно зафиксировано |
| Локальная сборка образа остановилась после установки 144 пакетов | Docker завис на сохранении тяжёлого слоя с PyTorch при том же лимите памяти | Сборка отменена вручную. Проверка `docker run --rm ... ls dataset` не выполнена |
| CI остановил deploy при загрузке образа в kind | Импорт образа занял больше заданных для job 10 минут; пользователь прогон не отменял | Лимит deploy увеличен до 30 минут |
| Airflow не стал `Ready` в [run 39309559546](https://github.com/AnnAnsas/MLPro/actions/runs/39309559546) | Две реплики сервиса, Airflow и мониторинг перегрузили kind; API Kubernetes перестал отвечать | Для переобучения HPA и сервис переводятся на одну реплику, запрос Airflow снижен с 768 до 512 МиБ |

