# Hermesser Minishop

![Hermesser Minishop](docs/hermesser_banner.webp)

Форк [remnawave-minishop](https://github.com/3252a8/remnawave-minishop) — Telegram-бот и Web App (Mini App) для продажи и управления подписками. Вся механика бота, админка, платежи, Mini App, тарифы, поддержка и промокоды — заслуга upstream-проекта. Мы переиспользуем этот стек для своего продукта, заменив транспортный слой и контент.

## Документация

Документация не менялась с форка:

- [Входная страница](docs/index.md)
- [Развертывание](docs/getting-started/deployment.md)
- [Настройка окружения](docs/getting-started/configuration.md)
- [Переменные `.env`](docs/configuration/env-vars.md)
- [Тарифы](docs/features/tariffs.md)
- [Админ-панель](docs/features/admin-panel.md)
- [Веб-приложение / Mini App](docs/features/web-app.md)
- [Telegram-авторизация](docs/features/telegram-auth.md) и [вход по email](docs/features/email-login.md)
- [Поддержка / тикеты](docs/features/support.md)
- [Бэкапы и восстановление](docs/features/backups.md)
- [Темы Web App](docs/features/webapp-themes.md)
- [Миграции](docs/migrations/index.md)
- [Рецепты для контрибьюторов](docs/development/how-to.md) (см. также [CONTRIBUTING.md](CONTRIBUTING.md))

## Стек

Сборка и runtime задаются `deploy/docker/Dockerfile` и `docker-compose.yml`; точные версии — в `backend/requirements.txt` и `frontend/package.json`.

| Слой | Технологии |
| --- | --- |
| Backend | Python **3.12**, [aiogram](https://docs.aiogram.dev/) 3.x, **aiohttp**, **SQLAlchemy** 2 async, **asyncpg**, **Pydantic** / pydantic-settings, **httpx**, платёжные SDK, **PyJWT** |
| Данные | **PostgreSQL** **17** и **Redis** **7** |
| Сборка Web App | **Node.js** **22**, **Svelte** **5**, **Vite**, **Tailwind CSS** 4; артефакты в `backend/bot/app/web/templates/` |

## Быстрый старт

Требования: Docker, Docker Compose, токен Telegram-бота, публичный домен.

```bash
git clone https://github.com/boudyai/hermesser-minishop
cd hermesser-minishop
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f backend worker frontend
```

Минимально заполните в `.env`:

- `BOT_TOKEN` — токен Telegram-бота;
- `ADMIN_IDS` — Telegram ID администраторов через запятую;
- `WEBHOOK_BASE_URL` — публичный URL вебхуков;
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — доступы PostgreSQL;
- `WEBAPP_ENABLED=True` — включает Web App и админку для первого входа;
- `WEBAPP_SESSION_SECRET`, `WEBHOOK_SECRET_TOKEN` — стабильные секреты;
- `SUBSCRIPTION_MINI_APP_URL` — публичный HTTPS URL Mini App;
- `TARIFFS_CONFIG_PATH=data/tariffs.json`;
- `TRUSTED_PROXIES` — CIDR/IP reverse-прокси для IP-allowlist платёжных webhook;
- остальные настройки — через Web App админку.

После первого входа в админку настройте тарифы (JSON-редактор), платёжные провайдеры, темы, поддержку и инструкции установки через UI.

```bash
mkdir -p data/themes data/webapp-logo data/tariffs
touch data/locales-overrides.json
chown -R 10001:10001 data
chmod -R u+rwX data
```

## Полезные команды

```bash
# Полная локальная проверка перед PR
npm run check

# Быстрый smoke-прогон
npm run check:quick

# Локальная сборка и запуск
docker compose up -d --build

# Логи
docker compose logs -f backend worker frontend

# Продакшен-вариант с Caddy
cd deploy/examples/caddy
cp .env.example .env
nano .env
docker compose up -d
```

## Имена образов

Форк собирается в те же образы, что и upstream:

- `ghcr.io/3252a8/remnawave-minishop-backend`
- `ghcr.io/3252a8/remnawave-minishop-worker`
- `ghcr.io/3252a8/remnawave-minishop-frontend`
- `docker.io/3252a8/remnawave-minishop-backend`
- `docker.io/3252a8/remnawave-minishop-worker`
- `docker.io/3252a8/remnawave-minishop-frontend`
