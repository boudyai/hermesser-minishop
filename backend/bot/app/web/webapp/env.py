"""Tenant .env editor endpoints for the webapp."""

import logging
from typing import Any

from aiohttp import web
from sqlalchemy.orm import sessionmaker

from bot.app.web.context import (
    get_session_factory,
    get_subscription_service,
)
from bot.app.web.webapp.common import (
    _json_error,
    _require_user_id,
)
from bot.app.web.webapp.response_helpers import json_response
from bot.services.hermes_provisioning_service import HermesProvisioningService
from bot.services.subscription_service_impl.core import SubscriptionService

logger = logging.getLogger(__name__)


async def _get_tenant_id(
    subscription_service: SubscriptionService, session: Any, user_id: int
) -> str | None:
    active = await subscription_service.get_active_subscription_details(session, user_id)
    if not active:
        return None
    return str(active.get("user_id") or "").strip() or None


async def env_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    async_session_factory: sessionmaker = get_session_factory(request)
    subscription_service: SubscriptionService = get_subscription_service(request)

    panel_service = getattr(subscription_service, "panel_service", None)
    if not isinstance(panel_service, HermesProvisioningService):
        return _json_error(503, "env_disabled", "Env editor not available")

    async with async_session_factory() as session:
        tenant_id = await _get_tenant_id(subscription_service, session, user_id)

    if not tenant_id:
        return _json_error(404, "no_active_subscription", "No active subscription")

    content = await panel_service.get_user_env(tenant_id)
    return json_response({"ok": True, "env_content": content})


async def env_update_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    async_session_factory: sessionmaker = get_session_factory(request)
    subscription_service: SubscriptionService = get_subscription_service(request)

    panel_service = getattr(subscription_service, "panel_service", None)
    if not isinstance(panel_service, HermesProvisioningService):
        return _json_error(503, "env_disabled", "Env editor not available")

    body = await request.json()
    content = str(body.get("env_content", ""))

    async with async_session_factory() as session:
        tenant_id = await _get_tenant_id(subscription_service, session, user_id)

    if not tenant_id:
        return _json_error(404, "no_active_subscription", "No active subscription")

    ok = await panel_service.set_user_env(tenant_id, content)
    if not ok:
        return _json_error(502, "env_update_failed", "Failed to update env")

    return json_response({"ok": True})
