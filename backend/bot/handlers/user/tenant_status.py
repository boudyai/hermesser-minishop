"""Hermes tenant status handlers split from tenant.py."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.subscription_service_impl.core import SubscriptionService
from config.settings import Settings

router = Router(name="user_tenant_status_router")


async def _get_hermes_panel(subscription_service: SubscriptionService):
    from bot.services.hermes_provisioning_service import HermesProvisioningService

    panel_service = getattr(subscription_service, "panel_service", None)
    if not isinstance(panel_service, HermesProvisioningService):
        return None
    return panel_service


async def _get_active_subscription_for_status(
    subscription_service: SubscriptionService, session: AsyncSession, user_id: int
) -> dict | None:
    return await subscription_service.get_active_subscription_details(session, user_id)


def _subscription_is_expired(active: dict | None) -> bool:
    if not active:
        return False
    panel_status = str(active.get("status_from_panel") or "").upper()
    if panel_status in ("EXPIRED", "DISABLED", "LIMITED"):
        return True
    end_date = active.get("end_date")
    if end_date is None:
        return False
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)
    return end_date <= datetime.now(UTC)


async def _reply_or_edit(
    message: types.Message | types.InaccessibleMessage,
    text: str,
    markup: types.InlineKeyboardMarkup,
    edit: bool,
) -> None:
    if not isinstance(message, types.Message):
        return
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=markup)


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
    if message.from_user is None:
        return
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
    target_message: types.Message | types.InaccessibleMessage | None,
    user_id: int,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    edit: bool,
    i18n_data: dict | None = None,
) -> None:
    if target_message is None:
        return
    # ponytail: fetch the active subscription dict ONCE here — both
    # tenant_id and the panel_status / end_date / status_from_panel
    # fields come from the same call, and the panel-side lookup it
    # triggers (remnawave /key/info or users/get) is the slow part.
    active = await _get_active_subscription_for_status(subscription_service, session, user_id)
    tenant_id = str((active or {}).get("user_id") or "").strip() or None
    panel_service = await _get_hermes_panel(subscription_service)
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")
    _ = lambda key, **kw: i18n.gettext(current_lang, key, **kw) if i18n else key

    if not tenant_id or panel_service is None:
        text = _(
            "tg_hermes_status_no_tenant",
            default="Bot is not running. Open the Mini App to activate.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="Menu"),
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

    # ponytail: subscription state gates container state. A user whose
    # remnawave sub expired but whose tenant container is still happily
    # running gets the suspended copy with a Renew button. Without this
    # we showed "Bot is active", which misled the user about why their
    # LLM calls were failing. We reuse the existing suspended state —
    # block + Renew CTA are the same for both an operator-initiated
    # suspension and an automatic subscription-driven one.
    if _subscription_is_expired(active):
        text = _(
            "tg_hermes_status_subscription_expired",
            default="Subscription expired. Renew your subscription to start the bot again.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("renew", default="Renew"),
                            callback_data="main_action:my_subscription",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="Menu"),
                            callback_data="main_action:back_to_main",
                        )
                    ],
                ]
            ),
            edit=edit,
        )
        return

    if tenant_status in ("deleting", "deleted", "archived"):
        text = _(
            "tg_hermes_status_deleted",
            default="Bot deleted. Open the Mini App to create a new one.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("create_bot", default="Create bot"),
                            callback_data="main_action:my_subscription",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="Menu"),
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
            default="Bot suspended. Renew your subscription to start it again.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("renew", default="Renew"),
                            callback_data="main_action:my_subscription",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="Menu"),
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
            default="Starting your bot… takes ~30 seconds.\nRepeat /status in a minute.",
        )
        await _reply_or_edit(
            target_message,
            text,
            types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("back_to_menu", default="Menu"),
                            callback_data="main_action:back_to_main",
                        )
                    ]
                ]
            ),
            edit=edit,
        )
        return

    # ponytail: bot /status used to fetch the LiteLLM quota and
    # append a "Budget: spent / max (remaining X)" line. That
    # confused users — the quota is for the underlying LLM
    # spend, not a money balance the customer manages, and
    # showing it in the status card alongside a "Restart" /
    # "Delete" menu invited support tickets about a metric
    # they can't top up from this surface. CornLLM top-up
    # lives in the Mini App Settings card and the admin
    # user detail; the bot status card just shows bot-level
    # actions.
    text = (
        _(
            "tg_hermes_status_active",
            default="Bot is active",
        )
        + "\n"
        + _(
            "tg_hermes_status_actions_hint",
            default="Use the buttons below to manage:",
        )
    )
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_("restart", default="Restart"),
                    callback_data="tenant:restart",
                ),
                types.InlineKeyboardButton(
                    text=_("logs", default="Logs"),
                    callback_data="tenant:logs",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=_("suspend", default="Suspend"),
                    callback_data="tenant:suspend",
                ),
                types.InlineKeyboardButton(
                    text=_("delete", default="Delete"),
                    callback_data="tenant:delete",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=_("back_to_menu", default="Menu"),
                    callback_data="main_action:back_to_main",
                )
            ],
        ]
    )
    await _reply_or_edit(target_message, text, markup, edit)
