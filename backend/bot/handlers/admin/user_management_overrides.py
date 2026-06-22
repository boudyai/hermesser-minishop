import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hcode
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline.admin_keyboards import get_back_to_admin_panel_keyboard
from bot.middlewares.i18n import JsonI18n
from bot.services.panel_api_service import PanelApiService
from bot.services.referral_service import ReferralService
from bot.services.subscription_service import SubscriptionService
from bot.states.admin_states import AdminStates
from bot.utils import get_message_content, send_direct_message
from bot.utils.callback_answer import (
    callback_data,
    callback_message,
    message_bot,
    message_from_user,
)
from bot.utils.telegram_markup import (
    is_profile_link_error,
    remove_profile_link_buttons,
)
from bot.utils.text_sanitizer import (
    sanitize_display_name,
    sanitize_username,
    username_for_display,
)
from config.settings import Settings
from config.tariffs_config import default_payment_currency_code_for_settings
from db.dal import message_log_dal, subscription_dal, user_dal
from db.models import User

from .user_management_common import (
    EMAIL_REGEX,
    USERNAME_REGEX,
    _admin_tariff_label,
    _admin_user_button_label,
    _admin_user_reference_label,
    _enabled_admin_period_tariffs,
    _enabled_admin_tariffs,
    _find_user_by_admin_input,
    _format_traffic_period,
    _format_used_with_period,
    _resolve_admin_period_tariff_key,
    _resolve_bot_username,
    router,
)

from .user_management_info import handle_refresh_user_card

async def handle_premium_override_menu(
    callback: types.CallbackQuery,
    state: FSMContext,
    user: User,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    i18n_instance,
    lang: str,
) -> None:
    """Show premium override sub-menu with current state and quick toggles."""
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)

    active_sub = await subscription_dal.get_active_subscription_by_user_id(session, user.user_id)
    if not active_sub:
        await callback.answer(_("admin_premium_override_no_subscription"), show_alert=True)
        return

    unlimited = bool(getattr(active_sub, "premium_unlimited_override", False))
    bonus_bytes = int(getattr(active_sub, "premium_bonus_bytes", 0) or 0)
    bonus_gb = bonus_bytes / (1024**3) if bonus_bytes else 0

    if unlimited:
        current_text = _("admin_premium_override_state_unlimited")
    elif bonus_bytes > 0:
        current_text = _("admin_premium_override_state_bonus", gb=f"{bonus_gb:.2f}")
    else:
        current_text = _("admin_premium_override_state_none")

    text = "\n".join(
        [
            f"<b>{_('admin_premium_override_title')}</b>",
            "",
            _("admin_premium_override_hint"),
            "",
            _("admin_premium_override_current", current=current_text),
        ]
    )

    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("admin_premium_override_btn_unlimited"),
        callback_data=f"user_action:premium_override_set_unlimited:{user.user_id}",
    )
    builder.button(
        text=_("admin_premium_override_btn_bonus"),
        callback_data=f"user_action:premium_override_set_bonus:{user.user_id}",
    )
    builder.button(
        text=_("admin_premium_override_btn_clear"),
        callback_data=f"user_action:premium_override_clear:{user.user_id}",
    )
    builder.button(
        text=_("admin_user_back_to_card_button"),
        callback_data=f"user_action:refresh:{user.user_id}",
    )
    builder.adjust(1, 1, 1, 1)

    try:
        await callback_message(callback).edit_text(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback_message(callback).answer(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    await state.update_data(target_user_id=user.user_id)
    await callback.answer()


async def handle_premium_override_apply(
    callback: types.CallbackQuery,
    user: User,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    settings: Settings,
    i18n_instance,
    lang: str,
    *,
    unlimited: bool,
    bonus_bytes: int,
) -> None:
    """Persist a premium override (unlimited or explicit bonus) on the active subscription."""
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)

    try:
        active_sub = await subscription_dal.get_active_subscription_by_user_id(
            session, user.user_id
        )
        if not active_sub:
            await callback.answer(_("admin_premium_override_no_subscription"), show_alert=True)
            return

        active_sub.premium_unlimited_override = bool(unlimited)
        active_sub.premium_bonus_bytes = max(0, int(bonus_bytes or 0))
        if unlimited:
            active_sub.premium_is_limited = False

        await message_log_dal.create_message_log_no_commit(
            session,
            {
                "user_id": callback.from_user.id if callback.from_user else user.user_id,
                "event_type": "admin:premium_override",
                "content": (f"unlimited={bool(unlimited)} bonus_bytes={int(bonus_bytes or 0)}"),
                "is_admin_event": True,
                "target_user_id": user.user_id,
                "timestamp": datetime.now(timezone.utc),
            },
        )
        await session.commit()

        await subscription_service.sync_premium_squad_access_to_panel(session, user.user_id)
        await session.commit()

        await callback.answer(_("admin_premium_override_saved"), show_alert=False)
        await handle_refresh_user_card(
            callback, user, subscription_service, session, settings, i18n_instance, lang
        )
    except Exception as exc:
        logging.error(
            "Failed to apply premium override for user %s: %s", user.user_id, exc, exc_info=True
        )
        await session.rollback()
        await callback.answer(_("admin_premium_override_save_error"), show_alert=True)


async def handle_premium_override_bonus_prompt(
    callback: types.CallbackQuery,
    state: FSMContext,
    user: User,
    i18n_instance,
    lang: str,
) -> None:
    """Ask admin for the bonus GB to grant."""
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    await state.update_data(target_user_id=user.user_id)
    await state.set_state(AdminStates.waiting_for_premium_override_bonus_gb)
    prompt = _("admin_premium_override_bonus_prompt", user_id=user.user_id)
    try:
        await callback_message(callback).edit_text(prompt)
    except Exception:
        await callback_message(callback).answer(prompt)
    await callback.answer()


def _admin_hwid_limit_state_text(
    get_text: Callable[..., str],
    hwid_device_limit: Optional[int],
    extra_hwid_devices: int = 0,
) -> str:
    if hwid_device_limit is None:
        return get_text("admin_hwid_limit_state_default")
    base_limit = int(hwid_device_limit)
    if base_limit == 0:
        return get_text("admin_hwid_limit_state_unlimited")
    extra = max(0, int(extra_hwid_devices or 0))
    if extra > 0:
        return get_text(
            "admin_hwid_limit_state_with_extra",
            total=base_limit + extra,
            base=base_limit,
            extra=extra,
        )
    return get_text("admin_hwid_limit_state_count", count=base_limit)


async def handle_hwid_limit_menu(
    callback: types.CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    i18n_instance,
    lang: str,
) -> None:
    """Show HWID device limit override controls."""
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)

    active_sub = await subscription_dal.get_active_subscription_by_user_id(session, user.user_id)
    if not active_sub:
        await callback.answer(_("admin_hwid_limit_no_subscription"), show_alert=True)
        return

    current_text = _admin_hwid_limit_state_text(
        _,
        getattr(active_sub, "hwid_device_limit", None),
        int(getattr(active_sub, "extra_hwid_devices", 0) or 0),
    )
    text = "\n".join(
        [
            f"<b>{_('admin_hwid_limit_title')}</b>",
            "",
            _("admin_hwid_limit_hint"),
            "",
            _("admin_hwid_limit_current", current=current_text),
        ]
    )

    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("admin_hwid_limit_btn_set_number"),
        callback_data=f"user_action:hwid_limit_set_number:{user.user_id}",
    )
    builder.button(
        text=_("admin_hwid_limit_btn_unlimited"),
        callback_data=f"user_action:hwid_limit_set_unlimited:{user.user_id}",
    )
    builder.button(
        text=_("admin_hwid_limit_btn_reset"),
        callback_data=f"user_action:hwid_limit_reset:{user.user_id}",
    )
    builder.button(
        text=_("admin_user_back_to_card_button"),
        callback_data=f"user_action:refresh:{user.user_id}",
    )
    builder.adjust(1, 1, 1, 1)

    try:
        await callback_message(callback).edit_text(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback_message(callback).answer(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    await state.update_data(target_user_id=user.user_id)
    await callback.answer()


async def handle_hwid_limit_apply(
    callback: types.CallbackQuery,
    user: User,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    settings: Settings,
    i18n_instance,
    lang: str,
    *,
    hwid_device_limit: Optional[int],
) -> None:
    """Persist a HWID device base limit override and push it to the panel."""
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)

    try:
        active_sub = await subscription_dal.get_active_subscription_by_user_id(
            session, user.user_id
        )
        if not active_sub:
            await callback.answer(_("admin_hwid_limit_no_subscription"), show_alert=True)
            return

        active_sub.hwid_device_limit = hwid_device_limit

        effective_limit = await subscription_service.sync_hwid_device_limit_to_panel(
            session, user.user_id
        )
        await message_log_dal.create_message_log_no_commit(
            session,
            {
                "user_id": callback.from_user.id if callback.from_user else user.user_id,
                "event_type": "admin:hwid_device_limit",
                "content": (
                    f"hwid_device_limit={hwid_device_limit!r} "
                    f"effective_hwid_device_limit={effective_limit!r}"
                ),
                "is_admin_event": True,
                "target_user_id": user.user_id,
                "timestamp": datetime.now(timezone.utc),
            },
        )
        await session.commit()

        await callback.answer(_("admin_hwid_limit_saved"), show_alert=False)
        await handle_refresh_user_card(
            callback, user, subscription_service, session, settings, i18n_instance, lang
        )
    except Exception as exc:
        logging.error(
            "Failed to apply HWID device limit for user %s: %s",
            user.user_id,
            exc,
            exc_info=True,
        )
        await session.rollback()
        await callback.answer(_("admin_hwid_limit_save_error"), show_alert=True)


async def handle_hwid_limit_prompt(
    callback: types.CallbackQuery,
    state: FSMContext,
    user: User,
    i18n_instance,
    lang: str,
) -> None:
    """Ask admin for an explicit HWID device limit."""
    _ = lambda key, **kwargs: i18n_instance.gettext(lang, key, **kwargs)
    await state.update_data(target_user_id=user.user_id)
    await state.set_state(AdminStates.waiting_for_hwid_device_limit)
    prompt = _("admin_hwid_limit_prompt", user_id=user.user_id)
    try:
        await callback_message(callback).edit_text(prompt)
    except Exception:
        await callback_message(callback).answer(prompt)
    await callback.answer()
