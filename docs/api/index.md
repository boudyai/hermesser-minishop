# API и интеграции

Этот раздел собирает все публичные технические контракты Remnawave Minishop:
HTTP API Mini App и админки, доменные события и API Python-плагинов.

## Быстрый старт

- [Интерактивная спецификация](/api/reference/) показывает текущий OpenAPI-контракт
  через Swagger UI. Она читает опубликованный [`/openapi.json`](/openapi.json).
- [HTTP-контракты](../architecture/http-api.md) описывают envelope ответов,
  авторизацию, пагинацию, не-JSON маршруты и правила typed route contracts.
- [Доменные события](../architecture/events.md) фиксируют payload-модели,
  event names и core-реакции.
- [API плагинов](../development/plugins.md) и
  [контракт плагинов](../development/plugin-contract.md) описывают расширение
  проекта без форка ядра.

## Источник правды

Машиночитаемый контракт HTTP API хранится в `docs/openapi.json`, а на сайте
публикуется как [`/openapi.json`](/openapi.json). Файл генерируется из живого
`aiohttp`-роутера и проверяется контрактными тестами, поэтому его нельзя править
руками.

После изменения HTTP-контракта регенерируйте артефакты:

```bash
PYTHONPATH=backend python -m bot.app.web.openapi
npm --prefix frontend run generate:api-types
```

Swagger UI на сайте - это только удобная витрина поверх `openapi.json`.
Контрактом остаются backend route contracts, сгенерированный OpenAPI-файл и
проверки drift-guard.
