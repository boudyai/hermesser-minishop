"""One-off: send a synthetic premium traffic warning like TariffTrafficWorker (text + top-up button).

Target chat (first match):
  1) Positional integer: ``python ... <telegram_user_id> [almost|depleted]``
  2) Environment variable ``TELEGRAM_TEST_CHAT_ID``
  3) First entry in ``ADMIN_IDS`` from app settings

No default Telegram ID is embedded in this script.
"""  # noqa: E501

import asyncio
import os
import sys

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.middlewares.i18n import JsonI18n
from bot.utils.mini_app_url import subscription_mini_app_topup_url
from config.settings import Settings


def _premium_topup_markup(
    settings: Settings, i18n: JsonI18n, user_lang: str
) -> InlineKeyboardMarkup:
    _ = lambda k, **kw: i18n.gettext(user_lang, k, **kw)
    url = subscription_mini_app_topup_url(settings, "premium")
    if url:
        btn = InlineKeyboardButton(
            text=_("traffic_warn_btn_topup_webapp_premium"),
            web_app=WebAppInfo(url=url),
        )
    else:
        btn = InlineKeyboardButton(
            text=_("traffic_warn_btn_topup_premium"),
            callback_data="tariff_topup:list",
        )
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


def _resolve_target_chat_id(settings: Settings) -> int:
    raw = (os.environ.get("TELEGRAM_TEST_CHAT_ID") or "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError as exc:
            raise SystemExit(f"TELEGRAM_TEST_CHAT_ID must be an integer, got {raw!r}") from exc
    admins = getattr(settings, "ADMIN_IDS", None) or []
    if not admins:
        raise SystemExit(
            "Set TELEGRAM_TEST_CHAT_ID or configure ADMIN_IDS in the environment, "
            "or pass a numeric Telegram user id as the first argument."
        )
    return int(admins[0])


def _resolve_chat_id_and_mode(settings: Settings) -> tuple[int, str]:
    args = [a.strip() for a in sys.argv[1:] if a.strip()]
    if not args:
        return _resolve_target_chat_id(settings), "almost"
    if args[0] in ("almost", "depleted"):
        return _resolve_target_chat_id(settings), args[0]
    try:
        chat_id = int(args[0])
    except ValueError as exc:
        raise SystemExit(
            "First argument must be a Telegram user id (integer) or a mode: almost | depleted.\n"
            "Examples:\n"
            "  python ... 123456789\n"
            "  python ... 123456789 depleted\n"
            "  python ... depleted\n"
            "  TELEGRAM_TEST_CHAT_ID=123456789 python ..."
        ) from exc
    mode = args[1] if len(args) > 1 else "almost"
    if mode not in ("almost", "depleted"):
        mode = "almost"
    return chat_id, mode


async def main() -> None:
    settings = Settings()
    chat_id, mode = _resolve_chat_id_and_mode(settings)
    default = (settings.DEFAULT_LANGUAGE or "ru").split("-", 1)[0]
    i18n = JsonI18n(path="locales", default=default)
    lang = default if default in i18n.locales_data else "ru"
    servers = "• EU-FR-01\n• EU-DE-02"
    usage = {"used": "4.1 GB", "remaining": "0.9 GB", "limit_total": "5.0 GB"}
    if mode == "depleted":
        body = i18n.gettext(
            lang,
            "traffic_warning_premium_depleted",
            tariff_name="Стандарт",
            servers=servers,
            **usage,
        )
    else:
        body = i18n.gettext(
            lang,
            "traffic_warning_premium_almost",
            tariff_name="Стандарт",
            left_pct=10,
            servers=servers,
            **usage,
        )
    markup = _premium_topup_markup(settings, i18n, lang)
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id,
            body,
            parse_mode="HTML",
            reply_markup=markup,
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
