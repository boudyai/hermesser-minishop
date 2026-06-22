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
from .user_management_cards import (
    _send_with_profile_link_fallback,
    format_user_card,
    get_user_card_keyboard,
)
from .user_management_browser import (
    process_user_search_handler,
    user_action_handler,
    user_search_prompt_handler,
    users_list_handler,
)
from .user_management_overrides import (
    _admin_hwid_limit_state_text,
    handle_hwid_limit_apply,
    handle_hwid_limit_menu,
    handle_hwid_limit_prompt,
    handle_premium_override_apply,
    handle_premium_override_bonus_prompt,
    handle_premium_override_menu,
)
from .user_management_subscription import (
    handle_add_subscription_days_prompt,
    handle_add_subscription_prompt,
    handle_change_tariff_apply,
    handle_change_tariff_menu,
    handle_reset_trial,
    handle_send_message_prompt,
    handle_toggle_ban,
    handle_traffic_grant_menu,
    handle_traffic_grant_prompt,
)
from .user_management_info import (
    _log_admin_user_deletion,
    handle_delete_user_prompt,
    handle_refresh_user_card,
    handle_view_user_invitees,
    handle_view_user_logs,
    process_delete_user_confirmation_handler,
)
from .user_management_state import (
    ban_user_prompt_handler,
    process_ban_user_handler,
    process_direct_message_handler,
    process_hwid_device_limit_handler,
    process_premium_override_bonus_handler,
    process_subscription_days_handler,
    process_traffic_grant_gb_handler,
    process_unban_user_handler,
    unban_user_prompt_handler,
    user_card_from_list_handler,
    view_banned_users_handler,
)
