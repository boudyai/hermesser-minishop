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
from bot.utils.callback_answer import safe_answer_callback
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
    i18n_data: dict,
) -> None:
    user_id = message.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    await _render_status(
        message,
        user_id,
        settings,
        subscription_service,
        session,
        edit=False,
        i18n_data=i18n_data,
    )


@router.callback_query(F.data == "tenant:status")
async def status_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    i18n_data: dict,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await _render_status(
        callback.message,
        user_id,
        settings,
        subscription_service,
        session,
        edit=True,
        i18n_data=i18n_data,
    )
    await callback.answer()


async def _render_status(
    target_message: "types.Message | types.InaccessibleMessage | None",
    user_id: int,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    edit: bool,
    i18n_data: dict | None = None,
) -> None:
    if target_message is None:
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    panel_service = await _get_hermes_panel(subscription_service)
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key

    if not tenant_id or panel_service is None:
        text = _(
            "tg_hermes_status_no_tenant",
            default="🤖 Bot is not running. Open the Mini App to activate.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="⬅️ Menu"),
                            callback_data="main_action:back_to_main",
                        )
                    ]
                ]
            ),
            edit=edit,
        )
        return

    tenant_state = await panel_service.get_tenant_state(tenant_id) or {}
    tenant_status = str(tenant_state.get("status") or "active").lower()

    if tenant_status in ("deleting", "deleted", "archived"):
        text = _(
            "tg_hermes_status_deleted",
            default="🗑 Bot deleted. Open the Mini App to create a new one.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("create_bot", default="🆕 Create bot"),
                            callback_data="main_action:my_subscription",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="⬅️ Menu"),
                            callback_data="main_action:back_to_main",
                        )
                    ],
                ]
            ),
            edit=edit,
        )
        return

    if tenant_status == "suspended":
        text = _(
            "tg_hermes_status_suspended",
            default="⏸ Bot suspended. Renew your subscription to start it again.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("renew", default="💳 Renew"),
                            callback_data="main_action:my_subscription",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="⬅️ Menu"),
                            callback_data="main_action:back_to_main",
                        )
                    ],
                ]
            ),
            edit=edit,
        )
        return

    if tenant_status in ("provisioning_vm", "provisioning_litellm_key", "created", "error"):
        text = _(
            "tg_hermes_status_provisioning",
            default="⏳ Starting your bot… takes ~30 seconds.\nRepeat /status in a minute.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="⬅️ Menu"),
                            callback_data="main_action:back_to_main",
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
        if max_b is not None and remaining is not None:
            quota_text = (
                f"\n💰 {_('budget_label', default='Budget')}: "
                f"{format_rub_pair(0, max_b, default='—')} "
                f"({_('remaining_label', default='remaining')} "
                f"{format_rub(remaining, default='—')})"
            )

    text = (
        _(
            "tg_hermes_status_active",
            default="🤖 Bot is active",
        )
        + f"{quota_text}\n"
        + _(
            "tg_hermes_status_actions_hint",
            default="Use the buttons below to manage:",
        )
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_("restart", default="🔄 Restart"),
                    callback_data="tenant:restart",
                ),
                types.InlineKeyboardButton(
                    text=_("logs", default="📋 Logs"),
                    callback_data="tenant:logs",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=_("suspend", default="⏸ Suspend"),
                    callback_data="tenant:suspend",
                ),
                types.InlineKeyboardButton(
                    text=_("delete", default="🗑 Delete"),
                    callback_data="tenant:delete",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=_("back_to_menu", default="⬅️ Menu"),
                    callback_data="main_action:back_to_main",
                )
            ],
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
async def restart_command(message: types.Message, i18n_data: dict) -> None:
    await _confirm_restart(message, edit=False, i18n_data=i18n_data)


@router.callback_query(F.data == "tenant:restart")
async def restart_callback(callback: types.CallbackQuery, i18n_data: dict) -> None:
    await _confirm_restart(callback.message, edit=True, i18n_data=i18n_data)
    await callback.answer()


async def _confirm_restart(
    target_message: "types.Message | types.InaccessibleMessage | None",
    edit: bool,
    i18n_data: dict | None = None,
) -> None:
    if target_message is None:
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    text = _(
        "tg_hermes_restart_confirm",
        default="🔄 Restart the bot?\n\nContainer will stop and start again (~30 seconds).",
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_("yes_restart", default="✅ Yes, restart"),
                    callback_data="tenant:restart:confirm",
                ),
                types.InlineKeyboardButton(
                    text=_("cancel", default="❌ Cancel"),
                    callback_data="tenant:status",
                ),
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
    i18n_data: dict,
) -> None:
    user_id = callback.from_user.id
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer(
            _("service_unavailable", default="Service unavailable"), show_alert=True
        )
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await callback.answer(_("no_active_bot", default="No active bot"), show_alert=True)
        return
    ok = await panel_service.restart_tenant(tenant_id)
    queued_msg = _(
        "tg_hermes_restart_queued",
        default="🔄 Restart queued. Bot returns in ~30 seconds.",
    )
    if ok:
        await safe_answer_callback(callback, queued_msg, show_alert=True)
    else:
        await safe_answer_callback(
            callback,
            _("tg_hermes_restart_failed", default="❌ Could not queue restart. Try again later."),
            show_alert=True,
        )
        return
    if callback.message:
        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                queued_msg,
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=_(
                                    key="tg_hermes_back_to_status_button",
                                    default="⬅️ Back to status",
                                ),
                                callback_data="tenant:status",
                            )
                        ]
                    ]
                ),
            )
        except Exception:
            try:
                await callback.message.answer(  # type: ignore[union-attr]
                    _(
                        "tg_hermes_restart_queued_inline",
                        default="🔄 Restart queued. Bot returns in ~30 seconds.",
                    )
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
    i18n_data: dict | None = None,
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
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer(
            _("service_unavailable", default="Service unavailable"), show_alert=True
        )
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
                text = "✅ " + _(
                    "tg_hermes_bot_creating",
                    default="Your bot @{username} is being created and will start in ~30 seconds.",
                    username=pending_username,
                )
            else:
                text = (
                    "⚠️ "
                    + _(
                        "tg_hermes_bot_creation_failed",
                        default=(
                            "Could not create the bot automatically. "
                            "Try again later or open the Mini App."
                        ),
                    )
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
    i18n_data: dict,
) -> None:
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await message.answer(
            _(
                "tg_hermes_command_only_in_hermes_mode",
                default="This command is only available in hermes mode.",
            )
        )
        return
    text = (
        "🔧 "
        + _("tg_hermes_token_intro_title", default="Enter your bot token from @BotFather:")
        + "\n\n"
        + _("tg_hermes_token_intro_format", default="Format: 123456789:ABCdef...")
        + "\n\n"
        + _("tg_hermes_token_intro_help", default="Create a bot: open @BotFather → /newbot")
    )
    await message.answer(text)
    await state.set_state(TokenFSM.waiting_for_token)


@router.callback_query(F.data == "main_action:set_token")
async def set_token_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    settings: Settings,
    i18n_data: dict,
) -> None:
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await state.set_state(TokenFSM.waiting_for_token)
    text = (
        "🔧 "
        + _("tg_hermes_token_intro_title", default="Enter your bot token from @BotFather:")
        + "\n\n"
        + _("tg_hermes_token_intro_format", default="Format: 123456789:ABCdef...")
        + "\n\n"
        + _("tg_hermes_token_intro_help", default="Create a bot: open @BotFather → /newbot")
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
    i18n_data: dict | None = None,
) -> None:
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    user_id = message.from_user.id if message.from_user else 0
    token = (message.text or "").strip()
    if not token or ":" not in token or not token.split(":", 1)[0].isdigit():
        await message.answer(
            _(
                "tg_hermes_token_invalid_format",
                default="❌ Invalid format. Enter a token like 123456789:ABCdef...",
            )
        )
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
                    await message.answer(
                        _(
                            "tg_hermes_token_rejected",
                            default=(
                                "❌ Telegram rejected this token. "
                                "Double-check with @BotFather."
                            ),
                        )
                    )
                    return
                bot_username = data.get("result", {}).get("username", "")
    except Exception:
        logger.exception("getMe validation failed for user %s", user_id)
        await message.answer(
            _(
                "tg_hermes_token_unreachable",
                default="❌ Could not reach Telegram. Try again later.",
            )
        )
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
        text = "✅ " + _(
            "tg_hermes_bot_creating_named",
            default=(
                "Your bot @{username} is being created "
                "and will start in ~30 seconds."
            ),
            username=bot_username,
        )
    elif applied_to_tenant:
        text = "✅ " + _(
            "tg_hermes_token_updated",
            default=(
                "Token saved! Your bot @{username} was updated "
                "and is restarting (~30 seconds)."
            ),
            username=bot_username,
        )
    elif tenant_uuid:
        text = "⚠️ " + _(
            "tg_hermes_token_saved_but_not_applied",
            default=(
                "Token saved locally but not applied to the running bot. "
                "Bot @{username} will keep using the old token until "
                "the next activation."
            ),
            username=bot_username,
        )
    else:
        text = "✅ " + _(
            "tg_hermes_token_saved_pending",
            default=(
                "Token saved! Your bot @{username} "
                "will start once you activate."
            ),
            username=bot_username,
        )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_(key="tg_hermes_main_menu_status_button", default="📊 Status"),
                    callback_data="tenant:status",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=_(key="back_to_menu_button", default="⬅️ Menu"),
                    callback_data="main_action:back_to_main",
                )
            ],
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
    i18n_data: dict | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    await _send_logs(
        message, user_id, settings, subscription_service, session, edit=False, i18n_data=i18n_data
    )


@router.callback_query(F.data == "tenant:logs")
async def logs_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    i18n_data: dict | None = None,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    await _send_logs(
        callback.message,
        user_id,
        settings,
        subscription_service,
        session,
        edit=True,
        i18n_data=i18n_data,
    )
    await callback.answer(_("tg_hermes_logs_refreshed_toast", default="Logs refreshed"))


@router.callback_query(F.data == "tenant:logs:refresh")
async def logs_refresh_callback(
    callback: types.CallbackQuery,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    i18n_data: dict | None = None,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer(
            _("service_unavailable", default="Service unavailable"), show_alert=True
        )
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await callback.answer(_("no_active_bot", default="No active bot"), show_alert=True)
        return
    await panel_service.refresh_tenant_logs(tenant_id)
    import asyncio

    await asyncio.sleep(2)
    await _send_logs(
        callback.message,
        user_id,
        settings,
        subscription_service,
        session,
        edit=True,
        i18n_data=i18n_data,
    )
    await callback.answer(_("tg_hermes_logs_updated_toast", default="Updated"))


async def _send_logs(
    target_message: "types.Message | types.InaccessibleMessage | None",
    user_id: int,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    edit: bool,
    i18n_data: dict | None = None,
) -> None:
    if target_message is None:
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        return
    logs = await panel_service.get_tenant_logs(tenant_id)
    snippet = logs[-3500:] if len(logs) > 3500 else logs
    text = (
        f"{_('tg_hermes_logs_header', count=len(snippet), default='📋 Logs ({count} chars):')}"
        f"\n\n<pre>{snippet or '(empty)'}</pre>"
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_(key="tg_hermes_logs_refresh_button", default="🔄 Refresh"),
                    callback_data="tenant:logs:refresh",
                ),
                types.InlineKeyboardButton(
                    text=_(key="tg_hermes_back_to_status_button", default="⬅️ Back to status"),
                    callback_data="tenant:status",
                ),
            ]
        ]
    )
    await _reply_or_edit(target_message, text, markup, edit)


# ============================================
# /suspend
# ============================================


@router.message(Command("suspend"))
async def suspend_command(
    message: types.Message, settings: Settings, i18n_data: dict | None = None
) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    await _confirm_suspend(message, edit=False, i18n_data=i18n_data)


@router.callback_query(F.data == "tenant:suspend")
async def suspend_callback(
    callback: types.CallbackQuery, settings: Settings, i18n_data: dict | None = None
) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    await _confirm_suspend(callback.message, edit=True, i18n_data=i18n_data)
    await callback.answer()


async def _confirm_suspend(
    target_message: "types.Message | types.InaccessibleMessage | None",
    edit: bool,
    i18n_data: dict | None = None,
) -> None:
    if target_message is None:
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    text = (
        "⏸ "
        + _("tg_hermes_suspend_confirm_body", default="Suspend the bot?\n\n")
        + _(
            "tg_hermes_suspend_confirm_footer",
            default=(
                "The container will stop and the CornLLM key will be blocked. "
                "You can resume the bot by renewing the subscription."
            ),
        )
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_(key="tg_hermes_suspend_confirm_button", default="✅ Yes, suspend"),
                    callback_data="tenant:suspend:confirm",
                ),
                types.InlineKeyboardButton(
                    text=_(key="tg_hermes_cancel_button", default="❌ Cancel"),
                    callback_data="tenant:status",
                ),
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
    i18n_data: dict | None = None,
) -> None:
    user_id = callback.from_user.id
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await callback.answer(
            _("service_unavailable", default="Service unavailable"),
            show_alert=True,
        )
        return
    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await callback.answer(_("no_active_bot", default="No active bot"), show_alert=True)
        return
    ok = await panel_service.update_user_status_on_panel(tenant_id, enable=False)
    text = (
        "⏸ " + _("tg_hermes_suspend_success", default="Bot suspended.")
        if ok
        else "❌ " + _("tg_hermes_suspend_failed", default="Could not suspend.")
    )
    if callback.message:
        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                text,
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=_(key="back_to_menu_button", default="⬅️ Menu"),
                                callback_data="main_action:back_to_main",
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
async def delete_command(
    message: types.Message,
    state: FSMContext,
    settings: Settings,
    i18n_data: dict | None = None,
) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    await state.set_state(DeleteFSM.waiting_for_confirmation)
    text = (
        "🗑 "
        + _("tg_hermes_delete_confirm_body", default="Delete the bot?\n\n")
        + _(
            "tg_hermes_delete_confirm_typed_footer",
            default=(
                "The container will stop and be deleted. "
                "Backups are kept for 30 days.\n\n"
                "Type <code>DELETE</code> to confirm."
            ),
        )
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_(key="tg_hermes_cancel_button", default="❌ Cancel"),
                    callback_data="tenant:status",
                )
            ]
        ]
    )
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "tenant:delete")
async def delete_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    settings: Settings,
    i18n_data: dict | None = None,
) -> None:
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() != "hermes":
        await callback.answer()
        return
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    await state.set_state(DeleteFSM.waiting_for_confirmation)
    text = "🗑 " + _(
        "tg_hermes_delete_confirm_typed_body",
        default="Delete the bot?\n\nType <code>DELETE</code> to confirm.",
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_(key="tg_hermes_cancel_button", default="❌ Cancel"),
                    callback_data="tenant:status",
                )
            ]
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
    i18n_data: dict | None = None,
) -> None:
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key
    if (message.text or "").strip() != "DELETE":
        await message.answer(
            _(
                "tg_hermes_delete_typed_hint",
                default="Type DELETE in capital letters to confirm, or press Cancel.",
            )
        )
        return

    user_id = message.from_user.id if message.from_user else 0
    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await state.clear()
        await message.answer(
            _(
                "tg_hermes_service_unavailable_short",
                default="Service unavailable.",
            )
        )
        return

    tenant_id = await _get_tenant_id(subscription_service, session, user_id)
    if not tenant_id:
        await state.clear()
        await message.answer(
            _(
                "tg_hermes_no_active_bot_short",
                default="No active bot.",
            )
        )
        return

    await state.clear()
    ok = await panel_service.delete_user_from_panel(tenant_id)
    text = (
        "🗑 " + _("tg_hermes_delete_success", default="Bot deleted. Backups are kept for 30 days.")
        if ok
        else "❌ " + _("tg_hermes_delete_failed", default="Could not delete.")
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_(key="back_to_menu_button", default="⬅️ Menu"),
                    callback_data="main_action:back_to_main",
                )
            ]
        ]
    )
    await message.answer(text, reply_markup=markup)
