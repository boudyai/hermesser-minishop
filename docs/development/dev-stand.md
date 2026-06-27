# Единый dev stand

Единый dev stand - это локальный Docker Compose стенд для ручной и
автоматизированной full-stack QA. Он поднимает Mini Shop, PostgreSQL, Redis,
локальную Remnawave Panel, Remnawave Subscription Page и сиды для тестовых
пользователей.

Канонический вход - npm-команды из корня репозитория:

```powershell
Copy-Item deploy/dev/remnawave-dev.env.example .env.remnawave-dev
npm run dev:stand:config
npm run dev:stand:up
```

Старые compose-файлы не являются отдельными dev stand:

- `docker-compose-dev.yml` - базовый локальный Mini Shop стек.
- `docker-compose.remnawave-dev.yml` - overlay с Remnawave, Subscription Page и
  dev-сидами. Именно вместе с базовым файлом он образует единый dev stand.
- `docker-compose.test.yml` - изолированный runner для backend test suite.
- `docker-compose.demo.yml` - nginx для статической docs-demo.
- `docker-compose.yml` - production-like запуск приложения, не QA-стенд.

## Версии

Пинованные версии, проверенные 2026-06-25:

- Remnawave Panel `v2.7.4` (`remnawave/backend:2.7.4`)
- Remnawave Subscription Page `7.2.4`
  (`remnawave/subscription-page:7.2.4`)

Чтобы обновить Remnawave, поменяйте в `.env.remnawave-dev`:

```env
REMNAWAVE_DEV_VERSION=2.7.4
REMNAWAVE_SUBSCRIPTION_PAGE_VERSION=7.2.4
```

Эти же версии зафиксированы в `deploy/dev/remnawave-versions.lock.json`.
Full-stack QA проверяет, что env example и lock-файл не разъехались.

## Переменные окружения

Файл `deploy/dev/remnawave-dev.env.example` уже содержит локальные безопасные
значения. Скопируйте его в `.env.remnawave-dev` и меняйте только локально:

```powershell
Copy-Item deploy/dev/remnawave-dev.env.example .env.remnawave-dev
```

По умолчанию Mini Shop работает в dry-run режиме записи в панель:

```env
PANEL_WRITE_MODE=dry_run
PANEL_DRY_RUN_VALIDATE_REMOTE=False
PANEL_DRY_RUN_SYNTHETIC_CREATE=True
```

Это удобно для QA: приложение читает живую локальную Remnawave Panel, но
опасные мутации можно прогонять без реального изменения panel-состояния. Если
нужен live-режим против локальной панели, замените токен на токен из Remnawave
Settings -> API Tokens и включите:

```env
PANEL_API_KEY=...
REMNAWAVE_DEV_API_TOKEN=...
PANEL_WRITE_MODE=live
PANEL_DRY_RUN_VALIDATE_REMOTE=True
```

Детерминированный `REMNAWAVE_DEV_API_TOKEN` из example сидируется SQL-файлом
`deploy/dev/seed-remnawave.sql`. Не меняйте
`REMNAWAVE_DEV_JWT_AUTH_SECRET`, если не заменяете этот токен.

Для автоматизированной QA в example включены только dev/test-safe хуки:

```env
QA_AUTH_ENABLED=True
QA_PAYMENT_ENABLED=True
QA_PAYMENT_SECRET=dev_qa_payment_secret_change_me
```

`QA_AUTH_ENABLED` возвращает одноразовый email-код в ответе
`/api/auth/email/request`, но только в `APP_RUNTIME_MODE=development|test`.
`QA_PAYMENT_ENABLED` включает локальный provider `qa`; его webhook принимает
только HMAC-подписанные payload через `X-QA-Payment-Signature`.

## Запуск

```powershell
npm run dev:stand:config
npm run dev:stand:up
npm run dev:stand:ps
```

Логи основных сервисов:

```powershell
npm run dev:stand:logs
```

Full-stack QA поверх поднятого стенда:

```powershell
$env:QA_FULLSTACK = "1"
$env:QA_API_BASE_URL = "http://127.0.0.1:8082"
$env:QA_WEBHOOK_BASE_URL = "http://127.0.0.1:8080"
$env:QA_FRONTEND_URL = "http://127.0.0.1:8082"
$env:QA_REMNAWAVE_HEALTH_URL = "http://127.0.0.1:3001/health"
$env:QA_DB_DSN = "postgresql://remnawave_minishop:remnawave_minishop@127.0.0.1:6768/remnawave_minishop"
$env:QA_PAYMENT_SECRET = "dev_qa_payment_secret_change_me"
npm run qa:fullstack
```

Без `QA_FULLSTACK=1` `tests/qa` пропускаются, чтобы обычный `pytest` не
зависел от Docker Compose.

Остановка без удаления БД:

```powershell
npm run dev:stand:down
```

Чтобы удалить локальные базы и сиды, выполните тот же compose `down -v`
вручную:

```powershell
docker compose --env-file .env.remnawave-dev `
  -f docker-compose-dev.yml `
  -f docker-compose.remnawave-dev.yml `
  --profile seed `
  down -v
```

## URL

- Mini Shop frontend: `http://127.0.0.1:8082`
- Mini Shop backend health: `http://127.0.0.1:8080/healthz`
- Mini Shop PostgreSQL: `127.0.0.1:6768`
- Remnawave Panel: `http://127.0.0.1:3000`
- Remnawave metrics health: `http://127.0.0.1:3001/health`
- Remnawave Subscription Page upstream: `http://127.0.0.1:3010`

Subscription Page требует reverse proxy с HTTPS для прямого браузерного
использования. В этом стенде `127.0.0.1:3010` - локальный upstream; plain HTTP
запрос может вернуть empty reply, даже если сервис здоров и подключен к
Remnawave Panel.

## Сиды

Профиль `seed` выполняет два идемпотентных SQL-файла:

- `deploy/dev/seed-minishop.sql` - пользователи, подписки и платежи Mini Shop.
- `deploy/dev/seed-remnawave.sql` - API token, пользователи Remnawave и
  привязка к `Default-Squad`.

Тестовые пользователи:

| Telegram/user ID | Email | Состояние |
| --- | --- | --- |
| `910000001` | `runes.admin@example.com` | активная standard-подписка, admin ID |
| `910000002` | `runes.active@example.com` | активная premium-подписка около лимита трафика |
| `910000003` | `runes.expired@example.com` | истекшая подписка |

Повторный запуск сидов:

```powershell
docker compose --env-file .env.remnawave-dev `
  -f docker-compose-dev.yml `
  -f docker-compose.remnawave-dev.yml `
  --profile seed `
  run --rm dev-seed
```

Overlay использует отдельные volumes
`remnawave-minishop-runes-dev-db-data` и
`remnawave-minishop-runes-dev-redis-data`, чтобы не портить старый локальный
dev-стек с другими кредами.

## Smoke-проверка стенда

```powershell
curl.exe -fsS http://127.0.0.1:8080/healthz
curl.exe -fsS http://127.0.0.1:3001/health
curl.exe -I -fsS http://127.0.0.1:8082/

docker compose --env-file .env.remnawave-dev `
  -f docker-compose-dev.yml `
  -f docker-compose.remnawave-dev.yml `
  --profile seed `
  exec -T postgres psql -U remnawave_minishop -d remnawave_minishop `
  -c "select count(*) from users; select count(*) from subscriptions; select count(*) from payments;"

docker compose --env-file .env.remnawave-dev `
  -f docker-compose-dev.yml `
  -f docker-compose.remnawave-dev.yml `
  --profile seed `
  exec -T remnawave-db psql -U postgres -d postgres `
  -c "select token_name from api_tokens where uuid='30000000-0000-4000-8000-000000000001'; select username from users where username like 'runes_%' order by username;"
```

## Автоматизация реальных QA-сценариев

Реальный QA-слой находится в `tests/qa` и запускается командой
`npm run qa:fullstack` поверх единого dev stand. Он покрывает сценарии, которые
не должен был покрывать mock-smoke из runes-плана: mock-smoke проверяет
статическую demo-сборку без backend, а full-stack QA проверяет живые auth,
CSRF, платежный webhook, admin-save и состояние БД.

Текущие сценарии:

- Email auth через `/api/auth/email/request` и `/api/auth/email/verify`.
- CSRF-protected пользовательский запрос `/api/account/language`.
- Создание платежа через `/api/payments` с provider `qa`.
- HMAC webhook `/webhook/qa-payment` и настоящий
  `finalize_successful_payment` с активацией подписки.
- Проверка `payments` и `subscriptions` в PostgreSQL после webhook.
- Admin login и сохранение `SERVER_STATUS_URL` через `/api/admin/settings`.
- Проверка Remnawave health и пина версий Panel/Subscription Page.

CI workflow `.github/workflows/fullstack-qa.yml` запускает этот слой на:

- `pull_request` в `main` и `dev`;
- `push` в `main` и `dev`;
- ручной `workflow_dispatch`.

При падении workflow прикладывает Docker Compose logs как artifact.
