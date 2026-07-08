# Hermesser Minishop

![Hermesser Minishop](docs/hermesser_banner.webp)

Telegram-бот и Web App (Mini App) для управляемого хостинга персонального Hermes Agent (Nous Research, MIT) в Telegram. Это **форк [remnawave-minishop](https://github.com/3252a8/remnawave-minishop)**, перепрофилированный под продукт **Hermesser Host** ([верхнеуровневая архитектура и ТЗ](../../initial-docs/hermes-hosting-tz.md), [карта интеграции с панелью](../../initial-docs/minishop-integration-map.md)).

Hermesser Host выдаёт каждому клиенту личный Hermes Agent, привязанный к его собственному Telegram-боту, работающий 24/7, с памятью и скиллами. Доступ к LLM — через наш LiteLLM-гейтвей. Монетизация — подписка в рублях через Platega/СБП.

## Что отличает этот форк от upstream remnawave-minishop

Upstream продаёт подписки на VPN-панель Remnawave. Мы переиспользуем всю поверхность (Telegram-бот, Mini App, админка, платежи, поддержка, тарифы) для продажи **хостинга Hermes-инстансов**. Конкретно:

- **Hermes-режим панели** (`PANEL_WRITE_MODE=hermes`). Вместо Remnawave Panel запросы на provision/deprovision/list идут в наш собственный [provisioning-core API](../provisioning-core/README.md) на VPS, который создаёт `microvm` (через `microvm.nix` CLI) на dacha-воркере. Раньше панель читалась, теперь — управляется.
- **CornLLM-баланс на тарифе** (`included_cornllm_balance_rub` в `data/tariffs.json`) — лимит на AI-запросы через LiteLLM, привязанный к подписке и обнуляющийся при продлении. Трафик/VPN-концепты скрыты в hermes-режиме; пользователь видит «баланс AI-ответов».
- **Без VPN-маркетинга в копи.** Карточки тарифов, локали (`locales/{ru,en}.json`) и email-шаблоны переписаны под «Telegram AI-агент за 400 ₽/мес», не «VPN за X ₽/мес». Тонкая очистка: ни слова «Remnawave», «squad» или «vpn» в пользовательских текстах. Платежи — только Platega/СБП; остальные провайдеры оставлены в коде, но в hermes-режиме не рекламируются.
- **Onboarding-визард** в Mini App для нового клиента: провести через «создай бота в BotFather → вставь токен → оплати» в три шага, с явным объяснением, что входит в тариф (контейнер 2 vCPU / 4 GB RAM, CornLLM-баланс, память между перезапусками).
- **SMTP через `services@cornspace.su`** (Timeweb). Настроены `SMTP_HOST`/`SMTP_PORT`/`SMTP_FROM_NAME=Hermesser Host`; email-аутентификация, письма о платежах и тикеты поддержки ходят через наш ящик, а не relay upstream.

Полная карта, что именно переписано, — в [initial-docs/minishop-integration-map.md](../../initial-docs/minishop-integration-map.md).

## Возможности

Для пользователей:

- вход через Telegram Mini App `initData` или Telegram OAuth / OpenID Connect (для обычного браузера), либо одноразовый email-код через наш SMTP;
- онбординг-визард в три шага: создать бота в BotFather → вставить токен → оплатить тариф в рублях через СБП;
- личный кабинет в Mini App: статус подписки, дата продления, баланс AI-ответов (CornLLM), ссылка на свой Telegram-бот;
- встроенные инструкции по установке Mini App: личный экран `/install` и публичная ссылка `/s/<token>` для пересылки инструкции;
- тикеты поддержки в Mini App с email-уведомлениями админу;
- продление подписки в один клик, досрочная докупка AI-баланса (продление = новый 30-дневный период + обновлённый баланс);
- пробный период (если включён в `.env`), промокоды, реферальная программа.

Для администраторов:

- админ-панель для Telegram-ID из `ADMIN_IDS` (вход только через Telegram, не по email);
- дашборд со статистикой: пользователи, активные подписки, платежи, состояние воркеров;
- каталог тарифов с двумя режимами биллинга — **period** (наш случай: 1/3/6/12 мес, раз в месяц списывается `included_cornllm_balance_rub`) и **traffic** (для гибкости, в hermes-режиме не используется);
- редактор JSON-каталога тарифов прямо в админке с live-превью и хостинг-полями: `vcpu`, `memory_gb`, `included_cornllm_balance_rub`;
- настройки поверх `.env` через Web App админку (без перезапуска контейнера) — `app_setting_overrides` в Postgres;
- ручная синхронизация состояния пользователей с provisioning-core.

## Стек

Сборка и runtime задаются `deploy/docker/Dockerfile` и `docker-compose.yml`; точные версии пакетов — в `backend/requirements.txt` и `frontend/package.json`.

| Слой | Технологии |
| --- | --- |
| Backend | Python **3.12**, [aiogram](https://docs.aiogram.dev/) 3.x (Telegram), **aiohttp** (HTTP и Web App), **SQLAlchemy** 2 async, **asyncpg**, **Pydantic** / pydantic-settings, **httpx**, **PyJWT** |
| Данные | **PostgreSQL** **17** (сервис `postgres` в Compose) и **Redis** **7** (сервис `redis`) |
| Сборка Web App | **Node.js** **22**, **Svelte** **5**, **Vite**, **Tailwind CSS** 4; артефакты попадают в `backend/bot/app/web/templates/` |
| Платежи | **Platega** (СБП, по умолчанию) — YooKassa / FreeKassa / Wata / Telegram Stars / остальные остаются в коде для будущих режимов, но в hermes-режиме не активируются |
| SMTP | **Timeweb** (`smtp.timeweb.ru:587` STARTTLS) — `services@cornspace.su` |
| Auth (web) | **Telegram OAuth** (`oauth.telegram.org`) + **email-code** через SMTP |
| Воркеры (отдельный репо) | `services/provisioning-core/` (FastAPI, VPS) + `services/hermesser-provisioner/` (systemd, dacha), см. [верхнеуровневый README](../../README.md) |

Локальная разработка без Docker возможна при установленных Python 3.12, PostgreSQL, Redis и (для пересборки фронта) Node 22; типичный сценарий — всё через Compose.

## Структура репозитория

```
hermesser/                         # верхнеуровневое рабочее дерево (см. ../../README.md)
├── initial-docs/                  # ТЗ и карта интеграции с панелью
├── services/
│   ├── minishop/                  # ← ВЫ ЗДЕСЬ: этот форк
│   ├── provisioning-core/         # FastAPI: источник истины по тенантам, воркерам, LiteLLM-ключам
│   └── hermesser-provisioner/     # Pull-воркер: microvm + LiteLLM admin на dacha
├── infra/
│   ├── tenant-runtime/            # Образ и лимиты клиентского контейнера
│   └── litellm/                   # Compose + config прокси + виртуальные ключи
└── deploy/nixos-worker/           # NixOS-модуль для dacha-воркера
```

`docs-site/` внутри этого форка — локальный генератор документации upstream-проекта; в нашей версии бо́льшая часть русскоязычной документации живёт в `../../initial-docs/`, а статусные отчёты — в `../../docs/`.

## Быстрый старт

> Полные инструкции — в [docs/getting-started/deployment.md](docs/getting-started/deployment.md) и в [верхнеуровневом README](../../README.md). Этот раздел — быстрый smoke-test локально.

Требования:

- Docker и Docker Compose;
- токен Telegram-бота;
- публичные домены для webhook (если включаете Platega webhook) и Mini App;
- (опционально) учётные данные SMTP, если хотите включить email-вход;
- (опционально) provisioning-core API, если хотите hermes-режим. Без него включается обычный Remnawave-режим (`PANEL_WRITE_MODE=panel` + `PANEL_API_URL` + `PANEL_API_KEY`).

```bash
cd services/minishop
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f backend worker frontend
```

Минимально заполните в `.env`:

- `BOT_TOKEN` — токен Telegram-бота;
- `ADMIN_IDS` — Telegram ID администраторов через запятую;
- `WEBHOOK_BASE_URL` — публичный URL вебхуков (например `https://hermesser.cornspace.su/`);
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — доступы PostgreSQL;
- `WEBAPP_ENABLED=True` — включает Web App и админку для первого входа;
- `WEBAPP_SESSION_SECRET`, `WEBHOOK_SECRET_TOKEN` — стабильные секреты;
- `WEBAPP_TITLE=Hermesser Host` (по умолчанию) — бренд в email-шаблонах и заголовке Mini App;
- `SUBSCRIPTION_MINI_APP_URL` — публичный HTTPS URL Mini App/frontend, например `https://hermesser.cornspace.su/`;
- `PLATEGA_*` — `PLATEGA_ENABLED=True`, `PLATEGA_SBP_ENABLED=True`, `PLATEGA_MERCHANT_ID`, `PLATEGA_SECRET`, `PLATEGA_BASE_URL=https://app.platega.io`, `PLATEGA_SBP_METHOD=2`, `PLATEGA_RETURN_URL`/`PLATEGA_FAILED_URL`;
- `TELEGRAM_OAUTH_*` — `TELEGRAM_OAUTH_CLIENT_ID` (= bot_id), `TELEGRAM_OAUTH_CLIENT_SECRET` (из my.telegram.org), `TELEGRAM_OAUTH_REQUEST_ACCESS=write`;
- `SMTP_*` — `SMTP_HOST=smtp.timeweb.ru`, `SMTP_PORT=587`, `SMTP_STARTTLS=true`, `SMTP_USERNAME=services@cornspace.su`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL=services@cornspace.su`, `SMTP_FROM_NAME=Hermesser Host`;
- `TARIFFS_CONFIG_PATH=data/tariffs.json`;
- `TRUSTED_PROXIES` — оставьте дефолт для Docker/Caddy/Nginx/Newt или укажите IP/CIDR своего reverse proxy, чтобы IP-allowlist платёжных webhook видел реального провайдера;
- `PANEL_WRITE_MODE=hermes` + `HERMES_PROVISIONING_API_URL` + `HERMES_PROVISIONING_API_KEY` для hermes-режима; либо `PANEL_WRITE_MODE=panel` + `PANEL_API_URL` + `PANEL_API_KEY` + `PANEL_WEBHOOK_SECRET` для классического Remnawave-режима;
- остальные настройки удобнее задать в Web App админке.

После первого входа в админку настройте тарифы (через встроенный JSON-редактор), платёжные провайдеры, темы Mini App, поддержку, уведомления и инструкции установки через UI. Каталог тарифов по умолчанию — `data/tariffs.json`; в нашей конфигурации два тарифа (`CornLLM included` / `Just hosting`) с полями `vcpu`, `memory_gb`, `included_cornllm_balance_rub`. Полный справочник env-переменных — [docs/configuration/env-vars.md](docs/configuration/env-vars.md).

В Docker файл `data/tariffs.json` должен быть доступен не только `backend` и `worker`, но и одноразовому сервису `migrate`: мигратор читает каталог тарифов при привязке существующих подписок к тарифу по умолчанию. В compose-файле весь `/app/data` смонтирован в `migrate`, `backend` и `worker`; если переносите compose вручную, сохраните одинаковый mount для всех трёх сервисов.

В compose-примерах `/app/data` монтируется из папки `./data` рядом с `docker-compose.yml`. Заранее создайте каталог и отдайте его пользователю контейнера. Это нужно для сохранения `data/tariffs.json`, каталога тем `data/themes` и кеша логотипа Web App:

```bash
mkdir -p data/themes data/webapp-logo data/tariffs
touch data/locales-overrides.json
chown -R 10001:10001 data
chmod -R u+rwX data
```

## Полезные команды

```bash
# Полная локальная проверка перед PR (ruff + mypy + pytest + svelte-check)
npm run check

# Быстрый smoke-прогон во время разработки
npm run check:quick

# Сборка Web App (бэкенд читает шаблон из backend/bot/app/web/templates/)
npm run build:webapp

# Локальная сборка и запуск всего стека
docker compose up -d --build

# Логи приложения
docker compose logs -f backend worker frontend

# Рекомендуемый продакшен-вариант с Caddy (сам выпускает и продлевает TLS)
cd deploy/examples/caddy      # или nginx, newt, no-proxy
cp .env.example .env
nano .env
docker compose up -d
```

## Совместимость с upstream

Бо́льшая часть кода — upstream [`3252a8/remnawave-minishop`](https://github.com/3252a8/remnawave-minishop) (`main`). При слиянии upstream-изменений имей в виду:

- `PANEL_WRITE_MODE=hermes` — наша добавка; upstream знает только `panel` (по умолчанию) и `dry_run`. Файлы: `backend/bot/services/hermes_provisioning_service.py`, `backend/bot/app/web/webapp/env.py`.
- `lifecycle_activation.py` и `lifecycle_details.py` пропускают `panel_sub_link_id` в hermes-режиме (у нас нет subscription-ссылки в provisioning-core).
- `email_templates*` переписаны под бренд `Hermesser Host`; если upstream поменяет тему — сохрани наш footer `Sent automatically by Hermesser Host`.
- `data/tariffs.json` имеет нестандартные поля `vcpu`, `memory_gb`, `included_cornllm_balance_rub` — `_serialize_plans` пробрасывает их в ответ `/api/me`, и `OnboardingWizard.svelte` их рендерит. Не удаляй при обновлении.

Карта точек замены — [`initial-docs/minishop-integration-map.md`](../../initial-docs/minishop-integration-map.md) и в коде через `// ponytail:`-комментарии у нестандартных мест.

## Документация

Локальная (`docs/`) — для upstream-функций, общих для всех режимов:

- [Входная страница документации](docs/index.md) — маршрут по установке, настройке, платежам, админке и диагностике.
- [Единый dev stand](docs/development/dev-stand.md) — локальный Docker Compose стенд с Mini Shop, панелью, Subscription Page, сидами и full-stack QA (`npm run qa:fullstack`).
- [Развертывание](docs/getting-started/deployment.md) — Docker Compose, Caddy, Nginx, Pangolin/Newt и запуск без обратного прокси.
- [Переменные `.env`](docs/configuration/env-vars.md) — полный справочник всех env-ключей по разделам.
- [Тарифы](docs/features/tariffs.md) — каталог тарифов, модели на срок и по трафику, обычные и premium-докупки, premium-сквады, смена тарифа, HWID-лимиты и обработка трафика.
- [Админ-панель](docs/features/admin-panel.md) — права доступа, настройки, редактор тарифов, premium-сквады и сохранение JSON-каталога.
- [Веб-приложение / Mini App](docs/features/web-app.md) — отдельный порт, домен, инструкции установки и реферальные ссылки.
- [Telegram-авторизация](docs/features/telegram-auth.md) и [вход по email](docs/features/email-login.md) — настройка BotFather/OAuth и SMTP-логина.
- [Поддержка пользователей / тикеты](docs/features/support.md) — тикеты в Mini App, входящий список админки, уведомления, лимиты и внешняя ссылка поддержки.

Верхнеуровневая (`../../docs/`, `../../initial-docs/`) — для контекста Hermesser Host:

- [Верхнеуровневый README](../../README.md) — статус, архитектура, hard invariants.
- [Ops playbook](../../docs/ops-playbook.md) — incident response, health checks, code shipping, Platega / SMTP / Telegram OAuth конфигурация.
- [ТЗ](../../initial-docs/hermes-hosting-tz.md) — цели продукта, hard invariants, тарифная модель, безопасность.
- [Карта интеграции с панелью](../../initial-docs/minishop-integration-map.md) — что именно заменено в форке, поверхность подмены provisioning-core.
- [Дизайн-ревью](../../docs/design-review.md) — OpenAPI, state-машины, схема БД.

## Имена образов

Форк собирается в образы `3252a8/remnawave-minishop-*` (те же имена, что у upstream — это сделано намеренно для совместимости CI-инфраструктуры). Сборка и пуш — `npm run docker:publish` или вручную через `docker buildx`.

- `ghcr.io/3252a8/remnawave-minishop-backend`
- `ghcr.io/3252a8/remnawave-minishop-worker`
- `ghcr.io/3252a8/remnawave-minishop-frontend`
- `docker.io/3252a8/remnawave-minishop-backend`
- `docker.io/3252a8/remnawave-minishop-worker`
- `docker.io/3252a8/remnawave-minishop-frontend`
