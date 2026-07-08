# Курс USD/RUB для CornLLM

## Где определён

Единственный источник курса — константа `RUB_PER_USD` в файле:

```
backend/bot/utils/currency_format.py  →  RUB_PER_USD = 80.0
```

**Больше нигде.** Ни в `.env`, ни в настройках, ни в JSON тарифов. Все конвертации (рубли → доллары и обратно) идут через этот файл.

## Конвертация

В том же файле определены хелперы:

| Хелпер | Направление | Где используется |
|---|---|---|
| `rub_to_usd(rub)` | RUB → USD | topups.py, lifecycle_activation.py, success.py, serializers.py |
| `usd_to_rub(usd)` | USD → RUB | format_rub() |
| `format_usd(usd)` | USD → строка "$X.XX" | балансы в UI |
| `format_rub(usd)` | USD → строка "X ₽" | **только цены подписок** |

## Что затронет смена курса

1. **Баланс CornLLM** — все отображения баланса в долларах (`$`). Администратор вводит сумму в рублях (поле `included_cornllm_balance_rub` в редакторе тарифов), а пользователь видит доллары.
2. **Пополнение CornLLM** — пользователь платит в рублях (через Platega/YooKassa), бэкенд конвертирует в доллары по курсу и отправляет в provisioning-core.
3. **Цены подписок** — остаются в рублях (`₽`). Курс на них не влияет.

## Как поменять курс

1. Отредактируйте `backend/bot/utils/currency_format.py`, строка:
   ```python
   RUB_PER_USD = 80.0
   ```

2. Обновите тест `tests/unit/test_currency_format.py`:
   - `test_usd_to_rub_uses_80_multiplier` — проверка нового курса
   - `test_rub_to_usd_converts_at_configured_rate` — обратная конвертация
   - `test_format_rub_*` — обновите ожидаемые значения в рублях

3. Обновите строки в `locales/ru.json` и `locales/en.json`:
   - `wa_topup_cornllm_description` — текст "1 USD = X ₽"
   - `wa_hermes_tariff_plus_bullets` — если жёстко зашита сумма в долларах

4. Обновите хардкод в `frontend/src/webapp/components/CornllmTopupCard.svelte` (текст "1 USD = X ₽")

5. Пересоберите и задеплойте:
   ```bash
   docker compose up -d --build backend worker frontend
   ```

## Проверка

После деплоя:
- Откройте Mini App → статус бота → баланс CornLLM должен быть в `$`
- Пополните CornLLM на минимальную сумму → сообщение об успехе должно быть в `$`
- В админке → детали пользователя → баланс CornLLM в `$`
- В админке → список пользователей → колонка CornLLM в `$`
- Цены подписок (`/buy`, карточки тарифов) — должны остаться в `₽`
