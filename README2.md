# Домашняя работа 2 — CI/CD

Пайплайн: [.github/workflows/ci.yml](.github/workflows/ci.yml).

| Пункт | Ссылка |
|---|---|
| Пайплайн | Зелёный прогон с `tests`, `build`, `deploy` https://github.com/AnnAnsas/MLPro/actions/runs/36337616624|
| Образ | Страница пакета GHCR с SHA-тегом https://github.com/AnnAnsas/MLPro/pkgs/container/my-service|
| Pull request | PR с красной и зелёной проверками https://github.com/AnnAnsas/MLPro/pull/4/commits - коммиты add deploy stage и fix pg_advisory_xact_lock|
| Неверный путь модели | Красный - https://github.com/AnnAnsas/MLPro/actions/runs/36339889000/job/108677965125 и зелёный - https://github.com/AnnAnsas/MLPro/actions/runs/36340894825/job/108680932503 прогоны, диагноз - в ConfigMap указан неверный путь к модели. Job deploy упал на шаге service: rollout завершился по таймауту. Диагностика показала FileNotFoundError при загрузке artifacts/tiny_sequence_transformer.joblib. После восстановления пути artifacts/tiny_sequence_transformer_v1.joblib приложение запустилось, пайплайн прошёл успешно.|
| Неверное имя Secret | Красный и зелёный прогоны, диагноз |
| Недостаточно памяти | Красный - https://github.com/AnnAnsas/MLPro/actions/runs/36341276351/job/108681942976 и зелёный прогоны, диагноз - Job deploy упал на шаге base: PostgreSQL не достиг готовности за 180 секунд. Под остался в состоянии Pending, узел ему не назначен (NODE none). До развёртывания my-service пайплайн не дошёл, поэтому диагностика приложения вернула NotFound. Полезно добавить diagnostics kubectl describe pods / kubectl get events --sort-by=.metadata.creationTimestamp |