"""Bot tenant management handlers (Stream S10).

Feature parity with Mini App for hermes mode. Uses aiogram's auto-injection
(dispatcher workflow_data) for settings, subscription_service, session.
"""

from __future__ import annotations

import logging

import aiohttp
from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.subscription_service_impl.core import SubscriptionService
from config.settings import Settings

logger = logging.getLogger(__name__)

router = Router(name="user_tenant_router")


# ============================================
# FSM states
# ============================================


class TokenFSM(StatesGroup):
    waiting_for_token = State()


class DeleteFSM(StatesGroup):
    waiting_for_confirmation = State()


# ============================================
# Helpers
# ============================================


async def _get_hermes_panel(subscription_service: SubscriptionService):
    from bot.services.hermes_provisioning_service import HermesProvisioningService

    panel_service = getattr(subscription_service, "panel_service", None)
    if not isinstance(panel_service, HermesProvisioningService):
        return None
    return panel_service


async def _get_tenant_id(
    subscription_service: SubscriptionService, session: AsyncSession, user_id: int
) -> str | None:
    active = await subscription_service.get_active_subscription_details(session, user_id)
    if not active:
        return None
    return str(active.get("user_id") or "").strip() or None


async def _safe_delete_message(message: types.Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


# ============================================
# /status
# ============================================


@router.message(Command("status"))
async def status_command(
    message: types.Message,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    await _render_status(message, user_id, settings, subscription_service, session, edit=False)


@router.callback_query(F.data == "tenant:status")
async def status_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await _render_status(
        callback.message, user_id, settings, subscription_service, session, edit=True
    )
    await callback.answer()


async def _render_status(
    target_message: "types.Message | types.InaccessibleMessage | None",
    user_id: int,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    edit: bool,
) -> None:
    if target_message is None:
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    panel_service = await _get_hermes_panel(subscription_service)

    if not tenant_id or panel_service is None:
        text = "🤖 Бот не запущен. Откройте Личный кабинет для активации."
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="⬅️ В меню", callback_data="main_action:back_to_main"
                        )
                    ]
                ]
            ),
            edit=edit,
        )
        return

    # ponytail: after the user deletes the bot in the Mini App, the local
    # subscription can stay `is_active=true` for a few minutes (no
    # synchronous panel callback), so the previous "always show active"
    # render is wrong. Pull the core's runtime state and surface the real
    # lifecycle (deleting / deleted / suspended / provisioning) instead.
    tenant_state = await panel_service.get_tenant_state(tenant_id) or {}
    tenant_status = str(tenant_state.get("status") or "active").lower()

    if tenant_status in ("deleting", "deleted", "archived"):
        text = "🗑 Бот удалён. Откройте Личный кабинет, чтобы создать нового."
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🆕 Создать бота",
                            callback_data="main_action:my_subscription",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="⬅️ В меню", callback_data="main_action:back_to_main"
                        )
                    ],
                ]
            ),
            edit=edit,
        )
        return

    if tenant_status == "suspended":
        text = "⏸ Бот приостановлен. Возобновите подписку, чтобы снова запустить."
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="💳 Продлить",
                            callback_data="main_action:my_subscription",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="⬅️ В меню", callback_data="main_action:back_to_main"
                        )
                    ],
                ]
            ),
            edit=edit,
        )
        return

    if tenant_status in ("provisioning_vm", "provisioning_litellm_key", "created", "error"):
        text = "⏳ Бот запускается… Это занимает ~30 секунд.\nПовторите /status через минуту."
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="⬅️ В меню", callback_data="main_action:back_to_main"
                        )
                    ]
                ]
            ),
            edit=edit,
        )
        return

    quota = await panel_service.get_tenant_quota(tenant_id)
    quota_text = ""
    if quota:
        from bot.utils.currency_format import format_rub, format_rub_pair

        max_b = quota.get("max_budget")
        remaining = quota.get("remaining")
        # ponytail: the Telegram /status used to render USD via
        # `f"${float(remaining):.2f}"` — but the rest of the bot
        # (Mini App card, my-subscription copy) is in rubles. Show
        # the same units everywhere; `format_rub_pair` keeps kopecks
        # when the value is fractional (e.g. "9.49 / 1500 ₽").
        if max_b is not None and remaining is not None:
            quota_text = f"\n💰 Бюджет: {format_rub_pair(0, max_b, default='—')} (осталось {format_rub(remaining, default='—')})"

    text = f"🤖 Бот активен{quota_text}\nИспользуйте кнопки ниже для управления:"
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🔄 Перезагрузить", callback_data="tenant:restart"),
                types.InlineKeyboardButton(text="📋 Логи", callback_data="tenant:logs"),
            ],
            [
                types.InlineKeyboardButton(text="⏸ Приостановить", callback_data="tenant:suspend"),
                types.InlineKeyboardButton(text="🗑 Удалить", callback_data="tenant:delete"),
            ],
            [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="main_action:back_to_main")],
        ]
    )
    await _reply_or_edit(target_message, text, markup, edit)


async def _reply_or_edit(
    message: "types.Message | types.InaccessibleMessage",
    text: str,
    markup: types.InlineKeyboardMarkup,
    edit: bool,
) -> None:
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)  # type: ignore[union-attr]
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=markup)


# ============================================
# /restart
# ============================================


@router.message(Command("restart"))
async def restart_command(message: types.Message) -> None:
    await _confirm_restart(message, edit=False)


@router.callback_query(F.data == "tenant:restart")
async def restart_callback(callback: types.CallbackQuery) -> None:
    await _confirm_restart(callback.message, edit=True)
    await callback.answer()


async def _confirm_restart(
    target_message: "types.Message | types.InaccessibleMessage | None", edit: bool
) -> None:
    if target_message is None:
        return
    text = "🔄 Перезагрузить бота?\n\nКонтейнер будет остановлен и запущен заново (~30 секунд)."
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Да, перезагрузить", callback_data="tenant:restart:confirm"
                ),
                types.InlineKeyboardButton(text="❌ Отмена", callback_data="tenant:status"),
            ]
        ]
    )
    await _reply_or_edit(target_message, text, markup, edit)


@router.callback_query(F.data == "tenant:restart:confirm")
async def restart_confirm_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    user_id = callback.from_user.id
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer("Сервис недоступен", show_alert=True)
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await callback.answer("Нет активного бота", show_alert=True)
        return
    ok = await panel_service.restart_tenant(tenant_id)
    if ok:
        await safe_answer_callback(
            callback,
            "🔄 Перезагрузка поставлена в очередь. Бот вернётся через ~30 секунд.",
            show_alert=True,
        )
    else:
        await safe_answer_callback(
            callback,
            "❌ Не удалось поставить в очередь. Попробуйте позже.",
            show_alert=True,
        )
        return
    if callback.message:
        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                "🔄 Перезагрузка поставлена в очередь. Бот вернётся через ~30 секунд.",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="⬅️ К статусу", callback_data="tenant:status"
                            )
                        ]
                    ]
                ),
            )
        except Exception:
            try:
                await callback.message.answer(  # type: ignore[union-attr]
                    "🔄 Перезагрузка поставлена в очередь. Бот вернётся через ~30 секунд."
                )
            except Exception:
                pass


# ============================================
# Bot creation entrypoint (token FSM + create/recreate)
# ============================================


async def ensure_bot_creation_entrypoint(
    callback: types.CallbackQuery,
    state: FSMContext,
    settings: Settings,
    subscription_service: SubscriptionService,
    async_session_factory,
) -> None:
    """Routes the user into the bot-creation flow used by the bot menu.

    In Hermes mode the bot menu's "Создать бота" / "Подписаться" buttons
    used to drop the user into the old proxy subscription options (the
    VPN-style price + payment method picker). That is the wrong surface:
    there is no proxy here, only hosted Hermes tenants. This entrypoint
    instead:
      - if the user already has a saved token AND a missing/deleted
        tenant AND an active subscription → call create_panel_user
        right now and show the standard "token saved, bot running" reply.
      - otherwise → enter the token FSM and ask for a BotFather token.

    Returns silently if Hermes mode is off or the panel service is
    unavailable.
    """
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer("Сервис недоступен", show_alert=True)
        return

    user_id = callback.from_user.id
    from db.dal import user_dal

    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if db_user is None or db_user.is_banned:
            await callback.answer("Доступ запрещён", show_alert=True)
            return

        # ponytail: if we already have a token and a deleted/missing
        # tenant plus an active subscription, jump straight to
        # create_panel_user. This mirrors the Mini App
        # /api/tenant/recreate flow. The actual run happens in the
        # background — the user gets a "running" status reply.
        has_active_sub = False
        try:
            active = await subscription_service.get_active_subscription_details(session, user_id)
            has_active_sub = bool(active)
        except Exception:
            has_active_sub = False

        panel_uuid = str(db_user.panel_user_uuid or "").strip()
        tenant_state = await panel_service.get_tenant_state(panel_uuid) if panel_uuid else None
        tenant_status = str((tenant_state or {}).get("status") or "").lower()
        tenant_missing = not panel_uuid or tenant_status in ("", "deleted", "archived")
        pending_token = str(getattr(db_user, "pending_bot_token", "") or "")
        pending_username = str(getattr(db_user, "pending_bot_username", "") or "")

        if pending_token and tenant_missing and has_active_sub:
            telegram_id = int(getattr(db_user, "telegram_id", 0) or user_id)
            username_on_panel = (
                f"tg_{telegram_id}" if telegram_id else f"hermes-{panel_uuid[:8] or 'new'}"
            )
            try:
                result = await panel_service.create_panel_user(
                    username_on_panel=username_on_panel,
                    telegram_id=telegram_id,
                    bot_token=pending_token,
                    bot_username=pending_username or None,
                )
            except Exception:
                logger.exception("ensure_bot_creation: create_panel_user failed for %s", user_id)
                result = None
            await callback.answer()
            if result and not result.get("error"):
                text = f"✅ Ваш бот @{pending_username} создаётся и запустится через ~30 секунд."
            else:
                text = (
                    "⚠️ Не удалось создать бота автоматически. Попробуйте позже или "
                    "откройте Личный кабинет."
                )
            if callback.message:
                try:
                    await callback.message.edit_text(text)
                except Exception:
                    pass
            return

    # No token (or no active subscription): drop into the token FSM.
    await set_token_callback(callback, state, settings)
    await callback.answer()


@router.message(Command("token"))
async def token_command(
    message: types.Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await message.answer("Эта команда доступна только в hermes mode.")
        return
    text = (
        "🔧 Введите токен вашего бота из @BotFather:\n\n"
        "Формат: 123456789:ABCdef...\n\n"
        "Создайте бота: откройте @BotFather → /newbot"
    )
    await message.answer(text)
    await state.set_state(TokenFSM.waiting_for_token)


@router.callback_query(F.data == "main_action:set_token")
async def set_token_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await state.set_state(TokenFSM.waiting_for_token)
    text = (
        "🔧 Введите токен вашего бота из @BotFather:\n\n"
        "Формат: 123456789:ABCdef...\n\n"
        "Создайте бота: откройте @BotFather → /newbot"
    )
    if callback.message:
        try:
            await callback.message.edit_text(text)
        except Exception:
            pass
    await callback.answer()


@router.message(StateFilter(TokenFSM.waiting_for_token))
async def token_input(
    message: types.Message,
    state: FSMContext,
    async_session_factory,
    subscription_service: "SubscriptionService | None" = None,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    token = (message.text or "").strip()
    if not token or ":" not in token or not token.split(":", 1)[0].isdigit():
        await message.answer("❌ Неверный формат. Введите токен вида 123456789:ABCdef...")
        return

    bot_username = ""
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    await message.answer("❌ Telegram отклонил этот токен. Проверьте @BotFather.")
                    return
                bot_username = data.get("result", {}).get("username", "")
    except Exception:
        logger.exception("getMe validation failed for user %s", user_id)
        await message.answer("❌ Не удалось связаться с Telegram. Попробуйте позже.")
        return

    from db.dal import user_dal

    applied_to_tenant = True
    tenant_uuid = ""
    created_via_bot = False
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            await state.clear()
            await _safe_delete_message(message)
            return
        db_user.pending_bot_token = token
        db_user.pending_bot_username = bot_username or db_user.pending_bot_username
        await session.commit()
        # ponytail: if a tenant already exists, push the new token to
        # provisioning-core so the worker drains update_secrets right
        # now. Without this, the token is just stored locally and the
        # running bot keeps using the old one until the next trial /
        # paid activation. Best-effort: failure surfaces in the reply.
        tenant_uuid = str(db_user.panel_user_uuid or "").strip()
        if subscription_service is not None:
            from bot.services.hermes_provisioning_service import (
                HermesProvisioningService,
            )

            panel_service = getattr(subscription_service, "panel_service", None)
            if isinstance(panel_service, HermesProvisioningService):
                if tenant_uuid:
                    try:
                        owner_telegram_id = int(getattr(db_user, "telegram_id", 0) or 0) or None
                        applied_to_tenant = await panel_service.update_tenant_bot_token(
                            tenant_uuid,
                            token,
                            bot_username=bot_username,
                            owner_telegram_id=owner_telegram_id,
                        )
                    except Exception:
                        logger.exception(
                            "update_tenant_bot_token failed for user %s tenant %s",
                            user_id,
                            tenant_uuid,
                        )
                        applied_to_tenant = False
                else:
                    # ponytail: bot menu flow — user typed a token but
                    # has no tenant yet. If they have an active
                    # subscription, run the same create_panel_user the
                    # Mini App uses, then the worker drains
                    # create_litellm_key + create_vm. Surfaces a
                    # "running" status reply instead of leaving them
                    # stuck at the token-saved page.
                    has_active_sub = False
                    try:
                        active = await subscription_service.get_active_subscription_details(
                            session, user_id
                        )
                        has_active_sub = bool(active)
                    except Exception:
                        has_active_sub = False
                    if has_active_sub:
                        telegram_id = int(getattr(db_user, "telegram_id", 0) or user_id)
                        username_on_panel = (
                            f"tg_{telegram_id}" if telegram_id else f"hermes-{user_id}"
                        )
                        try:
                            result = await panel_service.create_panel_user(
                                username_on_panel=username_on_panel,
                                telegram_id=telegram_id,
                                bot_token=token,
                                bot_username=bot_username or None,
                            )
                            if result and not result.get("error"):
                                created_via_bot = True
                                applied_to_tenant = True
                                tenant_uuid = str((result.get("response") or {}).get("uuid") or "")
                                if tenant_uuid:
                                    db_user.panel_user_uuid = tenant_uuid
                                    await session.commit()
                        except Exception:
                            logger.exception(
                                "create_panel_user from bot token flow failed for %s",
                                user_id,
                            )

    await state.clear()
    await _safe_delete_message(message)
    if created_via_bot:
        text = f"✅ Ваш бот @{bot_username} создаётся и запустится через ~30 секунд."
    elif applied_to_tenant:
        text = (
            f"✅ Токен сохранён! Ваш бот @{bot_username} обновлён и перезапускается (~30 секунд)."
        )
    elif tenant_uuid:
        text = (
            f"⚠️ Токен сохранён локально, но не применён к работающему боту. "
            f"Бот @{bot_username} продолжит работать со старым токеном до следующей активации."
        )
    else:
        text = f"✅ Токен сохранён! Ваш бот @{bot_username} будет запущен при активации."
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📊 Статус", callback_data="tenant:status")],
            [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="main_action:back_to_main")],
        ]
    )
    await message.answer(text, reply_markup=markup)


# ============================================
# /logs
# ============================================


@router.message(Command("logs"))
async def logs_command(
    message: types.Message,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    await _send_logs(message, user_id, settings, subscription_service, session, edit=False)


@router.callback_query(F.data == "tenant:logs")
async def logs_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await _send_logs(callback.message, user_id, settings, subscription_service, session, edit=True)
    await callback.answer("Логи обновлены")


@router.callback_query(F.data == "tenant:logs:refresh")
async def logs_refresh_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer("Сервис недоступен", show_alert=True)
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await callback.answer("Нет активного бота", show_alert=True)
        return
    await panel_service.refresh_tenant_logs(tenant_id)
    import asyncio

    await asyncio.sleep(2)
    await _send_logs(callback.message, user_id, settings, subscription_service, session, edit=True)
    await callback.answer("Обновлено")


async def _send_logs(
    target_message: "types.Message | types.InaccessibleMessage | None",
    user_id: int,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    edit: bool,
) -> None:
    if target_message is None:
        return
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        return
    logs = await panel_service.get_tenant_logs(tenant_id)
    snippet = logs[-3500:] if len(logs) > 3500 else logs
    text = f"📋 Логи ({len(snippet)} символов):\n\n<pre>{snippet or '(empty)'}</pre>"
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🔄 Обновить", callback_data="tenant:logs:refresh"),
                types.InlineKeyboardButton(text="⬅️ К статусу", callback_data="tenant:status"),
            ]
        ]
    )
    await _reply_or_edit(target_message, text, markup, edit)


# ============================================
# /suspend
# ============================================


@router.message(Command("suspend"))
async def suspend_command(message: types.Message, settings: Settings) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    await _confirm_suspend(message, edit=False)


@router.callback_query(F.data == "tenant:suspend")
async def suspend_callback(callback: types.CallbackQuery, settings: Settings) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await _confirm_suspend(callback.message, edit=True)
    await callback.answer()


async def _confirm_suspend(
    target_message: "types.Message | types.InaccessibleMessage | None", edit: bool
) -> None:
    if target_message is None:
        return
    text = (
        "⏸ Приостановить бота?\n\n"
        "Контейнер будет остановлен, а ключ CornLLM заблокирован.\n"
        "Вы сможете возобновить бота, оплатив подписку."
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Да, приостановить", callback_data="tenant:suspend:confirm"
                ),
                types.InlineKeyboardButton(text="❌ Отмена", callback_data="tenant:status"),
            ]
        ]
    )
    await _reply_or_edit(target_message, text, markup, edit)


@router.callback_query(F.data == "tenant:suspend:confirm")
async def suspend_confirm_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer("Сервис недоступен", show_alert=True)
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await callback.answer("Нет активного бота", show_alert=True)
        return
    ok = await panel_service.update_user_status_on_panel(tenant_id, enable=False)
    text = "⏸ Бот приостановлен." if ok else "❌ Не удалось приостановить."
    if callback.message:
        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                text,
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="⬅️ В меню", callback_data="main_action:back_to_main"
                            )
                        ]
                    ]
                ),
            )
        except Exception:
            pass
    await callback.answer()


# ============================================
# /delete FSM
# ============================================


@router.message(Command("delete"))
async def delete_command(message: types.Message, state: FSMContext, settings: Settings) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    await state.set_state(DeleteFSM.waiting_for_confirmation)
    text = (
        "🗑 Удалить бота?\n\n"
        "Контейнер будет остановлен и удалён. Бэкапы хранятся 30 дней.\n\n"
        "Для подтверждения введите: <code>DELETE</code>"
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="tenant:status")]
        ]
    )
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "tenant:delete")
async def delete_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await state.set_state(DeleteFSM.waiting_for_confirmation)
    text = "🗑 Удалить бота?\n\nДля подтверждения введите: <code>DELETE</code>"
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="tenant:status")]
        ]
    )
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[union-attr]
        except Exception:
            pass
    await callback.answer()


@router.message(StateFilter(DeleteFSM.waiting_for_confirmation))
async def delete_confirm_input(
    message: types.Message,
    state: FSMContext,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
) -> None:
    if (message.text or "").strip() != "DELETE":
        await message.answer(
            "Введите DELETE заглавными буквами для подтверждения, или нажмите Отмена."
        )
        return

    user_id = message.from_user.id if message.from_user else 0
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await state.clear()
        await message.answer("Сервис недоступен.")
        return

    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await state.clear()
        await message.answer("Нет активного бота.")
        return

    await state.clear()
    ok = await panel_service.delete_user_from_panel(tenant_id)
    text = "🗑 Бот удалён. Бэкапы хранятся 30 дней." if ok else "❌ Не удалось удалить."
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="main_action:back_to_main")]
        ]
    )
    await message.answer(text, reply_markup=markup)
