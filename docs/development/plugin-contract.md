# Контракт плагинов

Типизированный источник истины — [`../../backend/bot/plugins/spec.py`](../../backend/bot/plugins/spec.py).
Эта страница помогает сориентироваться, но не дублирует весь контракт.

Плагин наследуется от `Plugin` и переопределяет только нужные хуки:

- `setup(ctx)` — регистрация сервисов и подписок на события;
- `setup_bot(ctx, user_root, admin_root)` — подключение aiogram-роутеров;
- `setup_web(ctx, app, scope)` — добавление aiohttp routes;
- `worker_tasks(ctx)` — долгоживущие coroutine-задачи worker-процесса;
- `queue_handlers(ctx)` — обработчики webhook-очереди;
- `migrations()` — цепочка миграций плагина;
- `locales_dir()` — дополнительные JSON-каталоги локалей;
- `entitlements_provider()` — интеграция feature flags.

`PluginContext` содержит настройки, optional bot/dispatcher/session factory, i18n и общий словарь
`services`. Словарь `services` — публичная поверхность расширения; ключи должны быть строками,
а хуки должны терпеть отсутствие optional-полей в вспомогательных entrypoint'ах.

Для first-party core services и типизированного plugin-кода предпочитай helpers на контексте:

- `ctx.require_bot()`, `ctx.require_i18n()`, `ctx.require_session_factory()` — когда entrypoint
  обязан иметь runtime-объект;
- `ctx.panel_service`, `ctx.subscription_service`, `ctx.notification_service` и парные
  `ctx.require_*` helpers — typed доступ к core services без строковых ключей;
- `ctx.get_service("my_service", MyService)` / `ctx.require_service("my_service", MyService)` —
  runtime-проверяемый доступ к сервисам, добавленным плагином.

Прямой `ctx.services[...]` остается совместимым API для внешних плагинов и динамических ключей, но
новый first-party код должен идти через typed helpers, если ключ заранее известен.

Web-плагины получают один из двух scope из `bot.plugins.spec`:

- `WEB_SCOPE_WEBAPP` — Mini App и admin API;
- `WEB_SCOPE_WEBHOOKS` — payment, panel, health и Telegram webhook routes.

Подписчики доменных событий сохраняют публичную сигнатуру `(event_name, dict)`. Формы payload'ов
описаны в [`../architecture/events.md`](../architecture/events.md) и проверяются pydantic-моделями
в `bot.infra.event_payloads`, но внешние подписчики получают обычный плоский `dict`.

Минимальный runnable sample лежит в
[`../../examples/plugins/audit_logger_plugin`](../../examples/plugins/audit_logger_plugin). Он показывает
`setup`, `setup_web` и подписку через `bot.infra.events.subscribe`.

## Observability hooks

Core exposes no-op observability defaults in `bot.infra.observability`. Plugins may provide
`ctx.services["error_reporter"]` implementing `ErrorReporter` and/or `ctx.services["metrics"]`
implementing `Metrics` from their `setup(ctx)` hook. `PluginContext.error_reporter` and
`PluginContext.metrics` resolve plugin-provided implementations or fall back to no-op defaults.

The web and worker global error paths call the resolved `ErrorReporter` for unhandled handler
exceptions. Reporter failures are logged and never replace the original exception. The service
keys are additive extension points; existing plugin hook signatures stay unchanged.
