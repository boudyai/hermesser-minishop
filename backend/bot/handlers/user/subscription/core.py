import hashlib
import html
import logging
from collections.abc import Sized
from datetime import datetime
from typing import Any, Optional, Union

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline.user_keyboards import (
    callback_context_from_back_callback,
    callback_suffix_for_context,
    get_autorenew_confirm_keyboard,
    get_back_to_main_menu_markup,
    get_hwid_device_packages_keyboard,
    get_payment_method_keyboard,
    get_subscription_options_keyboard,
    get_tariff_catalog_keyboard,
    get_tariff_packages_keyboard,
    get_tariff_periods_keyboard,
    sale_mode_with_callback_context,
    tariff_purchase_back_callback,
)
from bot.middlewares.i18n import JsonI18n
from bot.payment_providers import provider_supports_recurring
from bot.payment_providers.shared import service_supports_recurring
from bot.services.panel_api_service import PanelApiService
from bot.services.subscription_service import SubscriptionService
from bot.utils.callback_answer import (
    callback_bot,
    callback_data,
    callback_message,
    message_from_user,
)
from bot.utils.install_links import (
    append_install_share_link_text,
    ensure_user_install_guide_links,
)
from config.settings import Settings
from config.tariffs_config import (
    default_currency_key_for_settings,
    default_payment_currency_code_for_settings,
)
from db.dal import subscription_dal, user_billing_dal
from db.models import Subscription

from .core_common import (
    _auto_renew_control_visible,
    _enabled_tariffs,
    _event_user_id,
    _format_premium_bytes,
    _format_premium_usage_limit,
    _has_multiple_enabled_tariffs,
    _hwid_callback_token,
    _recurring_service_for_subscription,
    _shorten_hwid_for_display,
    _tariff_purchase_markup,
    _tariff_purchase_text,
    _with_subscription_purchase_description,
    router,
)
from .core_purchase import (
    display_subscription_options,
    reshow_subscription_options_callback,
    select_tariff_callback,
    select_tariff_package_callback,
    select_tariff_period_callback,
)
from .core_status import (
    my_devices_command_handler,
    my_subscription_command_handler,
)
from .core_topup import (
    hwid_devices_list_callback,
    hwid_devices_package_callback,
    select_tariff_premium_package_callback,
    tariff_change_apply_callback,
    tariff_change_confirm_apply_callback,
    tariff_change_confirm_pay_callback,
    tariff_change_list_callback,
    tariff_change_pay_callback,
    tariff_change_select_callback,
    tariff_topup_list_callback,
)
from .core_autorenew import (
    autorenew_cancel_from_webhook_button,
    confirm_autorenew_handler,
    connect_command_handler,
    disconnect_device_handler,
    toggle_autorenew_handler,
)
