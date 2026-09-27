# Домашняя работа 2 — CI/CD

Пайплайн: [.github/workflows/ci.yml](.github/workflows/ci.yml).

| Пункт | Подтверждение | Результат / диагноз |
|---|---|---|
| Пайплайн | [Зелёный прогон](https://github.com/AnnAnsas/MLPro/actions/runs/36337616624) | Успешны `tests`, `build`, `deploy`. |
| Образ | [Пакет GHCR](https://github.com/AnnAnsas/MLPro/pkgs/container/my-service) | Образ с SHA-тегом. |
| Pull request | [История PR №4](https://github.com/AnnAnsas/MLPro/pull/4/commits); [PR №11](https://github.com/AnnAnsas/MLPro/pull/11): [красный](https://github.com/AnnAnsas/MLPro/actions/runs/36345205688/job/108692875535?pr=11) → [зелёный](https://github.com/AnnAnsas/MLPro/actions/runs/36345602592/job/108694110708) | В PR №11 намеренно завышен порог качества, следующим коммитом восстановлен порог из паспорта. |
| Неверный путь модели | [Красный](https://github.com/AnnAnsas/MLPro/actions/runs/36339889000/job/108677965125) → [зелёный](https://github.com/AnnAnsas/MLPro/actions/runs/36340894825/job/108680932503) | `deploy`, шаг `service`: таймаут rollout. В логах `FileNotFoundError` для `artifacts/tiny_sequence_transformer.joblib`. Исправлен путь на `artifacts/tiny_sequence_transformer_v1.joblib`. |
| Неверное имя Secret | [Красный](https://github.com/AnnAnsas/MLPro/actions/runs/36342219784); [повтор с расширенной диагностикой](https://github.com/AnnAnsas/MLPro/actions/runs/36343891279/job/108689288136) → [зелёный после исправления](https://github.com/AnnAnsas/MLPro/actions/runs/36345602592/job/108694110708) | `deploy`, шаг `service`: таймаут rollout, новый под в `CreateContainerConfigError`. События: `secret "my-service-secrets-wrong" not found`. PostgreSQL — `1/1 Running`. |
| Недостаточно памяти | [Красный](https://github.com/AnnAnsas/MLPro/actions/runs/36341276351/job/108681942976) → [зелёный](https://github.com/AnnAnsas/MLPro/actions/runs/36341896111) | `deploy`, шаг `base`: PostgreSQL не готов за 180 с, под `Pending`, узел не назначен. До развёртывания API выполнение не дошло. Сам по себе `Pending` без событий планировщика не доказывает нехватку памяти. |

## Ответы на вопросы

### 1. Сколько времени занял build и какой слой использовал кэш?

В [первом прогоне](https://github.com/AnnAnsas/MLPro/actions/runs/36337616624) job `build` занял 14 минут 22 секунды (862 секунды), во [втором](https://github.com/AnnAnsas/MLPro/actions/runs/36339889000) — 22 секунды, примерно в 39 раз меньше. На скриншоте ниже отметка `CACHED` есть у слоя `RUN uv sync --frozen --no-dev --no-install-project`, а также у копирования исходников, артефакта и остальных показанных слоёв. Docker восстановил кэш из GitHub Actions: команды и входные файлы этих слоёв не изменились. Установка зависимостей расположена до копирования кода, поэтому при изменениях только в `src/` слой зависимостей также может использоваться повторно.
![CACHED](images/docker-cached.png)

#### Задача 1 со звёздочкой: ускорение

Время job `deploy` в двух успешных прогонах:

| Прогон | Время deploy |
|---|---:|
| [Первый](https://github.com/AnnAnsas/MLPro/actions/runs/36337616624/job/108671842544) | 2 мин 28 с — 148 секунд |
| [Второй](https://github.com/AnnAnsas/MLPro/actions/runs/36340894825/job/108680932503) | 2 мин 30 с — 150 секунд |

Deploy не ускорился: второй запуск занял на 2 секунды больше. Отдельной оптимизации deploy не выполнялось: каждый прогон создаёт новый kind-кластер, скачивает образ и разворачивает PostgreSQL и API. Кэш слоёв используется в job `build` и напрямую не ускоряет эти действия; причину разницы в 2 секунды по одним итоговым временам определить нельзя.

Для шага `astral-sh/setup-uv@v7` зафиксированы 1 с в [первом запуске tests](https://github.com/AnnAnsas/MLPro/actions/runs/36337616624/job/108671376217) и 0 с во [втором](https://github.com/AnnAnsas/MLPro/actions/runs/36340894825/job/108680629283). Это округлённое время одного шага, а не всего job `tests`. Для полного сравнения трёх job ещё нужно добавить общую длительность `tests` до и после; эти два числа сами по себе не доказывают ускорение тестов.

### 2. Почему ImagePullBackOff может появиться при зелёном deploy?

В `k8s/deployment.yaml` первоначально указан образ `my_service:1.0`, а в кластер CI загружается образ из GHCR с тегом `sha-<SHA коммита>`. Между `kubectl apply` и `kubectl set image` поды первоначального ReplicaSet могут попытаться скачать отсутствующий образ и получить `ImagePullBackOff`. После обновления Deployment новые поды используют загруженный SHA-образ, а старые заменяются. Поэтому временная ошибка старых подов не делает прогон красным, если rollout новой версии успешно завершился.

### 3. Как пароль базы попадает из GitHub в под?

Пароль хранится в GitHub Actions Secret `DB_PASSWORD` и передаётся в переменную окружения шага `load secrets`. Этот шаг создаёт Kubernetes Secret `my-service-secrets` с ключами `POSTGRES_PASSWORD` и `DATABASE_URL`, причём пароль включается в строку подключения. PostgreSQL получает пароль через `secretKeyRef`, а API получает `DATABASE_URL` через `envFrom.secretRef`. ConfigMap предназначена для несекретных настроек; пароль нельзя хранить в её YAML в репозитории, а доступ к самому Kubernetes Secret тоже необходимо ограничивать.

### 4. Что произойдёт, если убрать needs: tests у build?

Без `needs: tests` сборка сможет выполняться параллельно с тестами. Например, интеграционный тест обнаружит, что сервис не пишет предсказания в PostgreSQL, но build уже успеет опубликовать неисправный образ. Job `deploy`, зависящий от build, сможет начать развёртывание независимо от результата tests. Зависимость не позволяет передать дальше образ из коммита, который не прошёл проверки.

### 5. Почему на pull request запускаются только тесты?

У job `build` стоит условие `if: github.ref == 'refs/heads/main'`. Для события pull request GitHub использует ref вида `refs/pull/<номер>/merge`, поэтому build пропускается; deploy также пропускается из-за зависимости `needs: build`. После merge происходит push в `main`, и при успешных тестах запускается вся цепочка. Так изменения проверяются до слияния, а образ публикуется и развёртывается после него.

### 6. Зачем в init() используется pg_advisory_xact_lock?

В Kubernetes запущены две реплики API, и каждая при старте вызывает `init()` для одной базы. `pg_advisory_xact_lock(7001)` разрешает выполнять создание и обновление таблицы только одной такой транзакции, пока другая ждёт. Без блокировки при одновременном старте на пустой базе возможна гонка создания объектов, даже с `CREATE TABLE IF NOT EXISTS`. Блокировка освобождается при завершении транзакции; речь о репликах API, а не PostgreSQL.

### 7. В каком порядке возникают состояния подов при трёх поломках?

По этапам запуска порядок такой: `Pending` → `CreateContainerConfigError` → `CrashLoopBackOff`. При нехватке запрошенной памяти под не получает узел и остаётся `Pending`; именно отсутствие назначенного узла видно в [прогоне с поломкой ресурсов](https://github.com/AnnAnsas/MLPro/actions/runs/36341276351/job/108681942976). При неверном имени Secret контейнер нельзя подготовить к запуску (`CreateContainerConfigError`), а при неверном пути модели приложение уже запускается и падает с `FileNotFoundError`, после повторных падений переходя в `CrashLoopBackOff`. Это отдельные эксперименты, расположенные по этапам жизни пода, а не последовательность состояний одного пода.

## Задача 2 со звёздочкой: расширенная диагностика

В шаг `diagnostics` добавлены состояния Deployment, ReplicaSet и подов, `describe pods`, события кластера и текущие/предыдущие логи контейнеров каждого пода.

Проверка: [красный прогон с неверным именем Secret](https://github.com/AnnAnsas/MLPro/actions/runs/36343891279/job/108689288136).

Новый под `my-service-d698f4b69-b98rn` получил статус `CreateContainerConfigError`. В его событиях указано `Error: secret "my-service-secrets-wrong" not found`. Образ из GHCR уже присутствовал на узле, но обязательный Secret отсутствовал, поэтому контейнер не запустился и rollout завершился по таймауту.

Старые поды другого ReplicaSet получили `ImagePullBackOff` / `ErrImagePull`, пытаясь скачать `my_service:1.0`. Это отдельная ошибка старого образа. PostgreSQL был готов (`1/1 Running`). Расширенная диагностика позволила увидеть причину отказа нового пода, которую не показывали логи одного старого пода. Предыдущих логов у нового пода нет, поскольку его контейнер ещё не запускался.

## Задача 3 со звёздочкой: тест качества модели

Тест [`test_model_quality`](tests/test_quality.py) загружает сохранённую модель и фиксированную тестовую выборку [`model_quality.npz`](tests/data/model_quality.npz): 180 синтетических окон из ноутбука обучения, не входивших в train и validation. Он считает F1; значение в паспорте модели (`metadata.test_metrics.f1`) равно 1.0. Это результат на простой синтетической выборке, а не оценка качества на реальных данных.

Первым выполнен [красный прогон в PR №11](https://github.com/AnnAnsas/MLPro/actions/runs/36345205688/job/108692875535?pr=11): порог намеренно поднят до 1.01, недостижимого для F1. Проверка падает с сообщением:

```text
AssertionError: F1=1.0000, требуется >= 1.0100
```

В следующем коммите `62c1c7f` восстановлено сравнение с числом из паспорта:

```python
min_f1 = bundle["metadata"]["test_metrics"]["f1"]
```

[Зелёный прогон после исправления](https://github.com/AnnAnsas/MLPro/actions/runs/36345602592/job/108694110708). Красный прогон в PR подтверждает отказ теста качества, но сам по себе не доказывает блокировку сборки этим тестом: на PR сборка также отключена условием `github.ref == 'refs/heads/main'`. Для отдельного подтверждения блокировки через `needs: tests` нужен соответствующий прогон в main.

## Журнал проблем вне намеренных поломок

| Ошибка | Как нашла причину | Исправление |
|---|---|---|
| `I001`, `F401`, `E501`, `UP017` при `ruff check .` | Ruff указал ячейки ноутбука и импорты API: порядок импортов, неиспользуемый импорт, длинная строка и `timezone.utc`. | Отсортированы импорты, удалён неиспользуемый `validate_sequences`, перенесена длинная строка, использован `datetime.UTC`. |
| `F811: Redefinition of unused save_prediction` | После слияния в `db.py` остались две версии одной функции. | Удалена старая версия; сохранена запись `status_code` и `scores`. |
| `function pg_advsory_xact_lock(integer) does not exist` | Интеграционный тест упал в `db.init()`. В SQL была опечатка в имени функции. | Исправлено на `pg_advisory_xact_lock(7001)` в [коммите 68ef0d3](https://github.com/AnnAnsas/MLPro/commit/68ef0d39e647314747fbfdbcd41253a46a2b3f2a). |
| Несовпадение имени образа в build и deploy | При сверке workflow обнаружены разные правила формирования имени образа. | В обоих job используется `ghcr.io/<owner в нижнем регистре>/my-service:sha-<GITHUB_SHA>`; deploy загружает этот же образ в kind. |
