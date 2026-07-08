"""CornLLM (LiteLLM) top-up webapp endpoint.

The user picks an amount (>= 100 RUB, no upper limit), this endpoint
builds a ``WebAppPaymentContext`` with ``sale_mode="cornllm_topup"`` and
delegates to the same provider factory used for subscription
payments. The provider creates a hosted payment URL; on success the
shop webhook calls ``SubscriptionService.activate_cornllm_topup``,
which converts the amount to USD (1 USD = 100 RUB) and bumps the
tenant's ``litellm_keys.max_budget`` via provisioning-core.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from aiohttp import web
from sqlalchemy.orm import sessionmaker

from bot.app.web.context import (
    get_i18n,
    get_session_factory,
    get_settings,
)
from bot.app.web.webapp.auth import _require_user_id
from bot.app.web.webapp.common import _json_error, _parse_model_payload
from bot.app.web.webapp.payloads import WebAppCornllmTopupPayload
from bot.middlewares.i18n import get_i18n_instance
from bot.payment_providers import WebAppPaymentContext, get_provider_spec
from config.settings import Settings
from config.tariffs_config import default_payment_currency_code_for_settings
from db.dal import user_dal

logger = logging.getLogger(__name__)


def _cornllm_topup_description(
    lang: str, amount_rub: float, i18n_instance: Optional[Any] = None
) -> str:
    i18n_instance = i18n_instance or get_i18n_instance()
    return i18n_instance.gettext(lang, "tg_cornllm_topup_description", amount=amount_rub)


async def cornllm_topup_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    payload = await _parse_model_payload(request, WebAppCornllmTopupPayload)
    method = str(payload.method or "").strip().lower()
    if not method:
        return _json_error(400, "invalid_method", "Payment method is required")

    settings: Settings = get_settings(request)
    is_hermes = str(getattr(settings.panel_settings, "write_mode", "") or "").lower() == "hermes"
    if not is_hermes:
        return _json_error(
            503, "hermes_disabled", "CornLLM top-up is only available in Hermes mode"
        )

    session_factory: sessionmaker = get_session_factory(request)
    async with session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")
        if not db_user.panel_user_uuid:
            return _json_error(
                400,
                "no_active_subscription",
                "Active subscription is required for CornLLM top-up",
            )
        lang = db_user.language_code or settings.DEFAULT_LANGUAGE

        currency_code = default_payment_currency_code_for_settings(settings)
        amount_rub = float(payload.amount_rub)
        i18n_instance = get_i18n(request)

        provider_spec = get_provider_spec(method)
        if not provider_spec or not provider_spec.create_webapp_payment:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        if not provider_spec.is_visible_for_user(settings, request.app, is_admin=False):
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        if not provider_spec.is_usable_for_payment_currency(settings, currency_code):
            return _json_error(
                400, "unsupported_currency", "Payment method does not support this currency"
            )
        if not provider_spec.is_usable_for_payment_amount(settings, currency_code, amount_rub):
            return _json_error(
                400, "payment_amount_below_minimum", "Payment amount is below the provider minimum"
            )

        ctx = WebAppPaymentContext(
            request=request,
            session=session,
            user_id=user_id,
            method=method,
            # ponytail: months=0 marks the payment as non-subscription
            # and non-traffic; the activation path keys off sale_mode.
            months=0,
            price=amount_rub,
            stars_price=None,
            currency=currency_code,
            description=_cornllm_topup_description(lang, amount_rub, i18n_instance),
            sale_mode="cornllm_topup",
            traffic_gb=None,
        )
        if provider_spec.reuse_webapp_payment:
            from bot.payment_providers.shared import reusable_webapp_payment_response

            try:
                reusable = await reusable_webapp_payment_response(ctx, provider_spec)
            except Exception:
                logger.exception("CornLLM top-up: reusable probe failed for user %s", user_id)
                reusable = None
            if reusable is not None:
                return reusable
        return await provider_spec.create_webapp_payment(ctx)
