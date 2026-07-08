# Курс USD/RUB

Магазин работает в USD. Курс `USD_EXCHANGE_RATE` (рублей за 1 USD) нужен **только** когда Platega СБП требует сумму в рублях — при создании платежа backend умножает USD-цену на курс и отправляет RUB в Platega.

Platega Crypto работает напрямую в USD, без конвертации.

## Где определён

Переменная окружения `USD_EXCHANGE_RATE` в `.env`:

```bash
# Default: 100
USD_EXCHANGE_RATE=80
```

Код читает её в `backend/bot/utils/currency_format.py`:

```python
USD_EXCHANGE_RATE = float(os.getenv("USD_EXCHANGE_RATE", "100.0"))
```

**Больше нигде.** Не в настройках, не в JSON тарифов.

## Конвертация

В том же файле определены хелперы:

| Хелпер | Направление | Где используется |
|---|---|---|
| `usd_to_rub(usd)` | USD → RUB | Platega SBP: создание платежа (service.py:713) |
| `rub_to_usd(rub)` | RUB → USD | Конвертация `included_cornllm_balance_rub` в USD-кредит |
| `format_usd(usd)` | USD → строка "$X.XX" | Все отображения цен и балансов |
| `format_rub(usd)` | USD → строка "X ₽" | Legacy, не используется в новом коде |

## Что затронет смена курса

1. **Цены в Platega СБП** — сумма в рублях, которую получит Platega: `цена_в_USD × USD_EXCHANGE_RATE`.
2. **Ежемесячный CornLLM-кредит** — `included_cornllm_balance_rub / USD_EXCHANGE_RATE = USD`.
3. **Platega Crypto** — не затронут (работает в USD).
4. **Отображение в UI** — не затронуто (всё в `$`).

## Как поменять курс

1. Отредактируйте `USD_EXCHANGE_RATE` в `.env` на VPS:
   ```bash
   USD_EXCHANGE_RATE=80
   ```

2. Перезапустите контейнеры (env_file перечитывается):
   ```bash
   cd /opt/hermesser-minishop
   docker compose up -d backend worker frontend
   ```

   **Сборка не нужна** — переменная читается из `.env` в рантайме.

3. При необходимости обновите тарифы в админке (Admin → Tariffs) — цены теперь в USD.

## Проверка

После смены курса:
- Platega СБП должен создавать платёж в рублях по новому курсу
- CornLLM-кредит при активации подписки должен начисляться по новому курсу
- Отображение цен и балансов в `$` не должно измениться
