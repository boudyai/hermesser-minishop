"""Tenant management endpoints for the webapp (env editor, restart, quota, logs)."""

import logging
from typing import Any

from aiohttp import web
from sqlalchemy.orm import sessionmaker

from bot.app.web.context import (
    get_i18n,
    get_session_factory,
    get_subscription_service,
)
from bot.app.web.webapp.common import (
    _json_error,
    _require_user_id,
)
from bot.app.web.webapp.response_helpers import json_response
from bot.middlewares.i18n import get_i18n_instance
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


async def _get_hermes_panel_service(
    subscription_service: SubscriptionService,
) -> HermesProvisioningService | None:
    panel_service = getattr(subscription_service, "panel_service", None)
    if not isinstance(panel_service, HermesProvisioningService):
        return None
    return panel_service


async def _resolve_tenant(
    request: web.Request,
) -> tuple[HermesProvisioningService, str] | web.Response:
    """Resolve the caller's HermesProvisioningService + tenant_id, or return an error response."""
    user_id = _require_user_id(request)
    async_session_factory: sessionmaker = get_session_factory(request)
    subscription_service: SubscriptionService = get_subscription_service(request)

    panel_service = await _get_hermes_panel_service(subscription_service)
    if panel_service is None:
        return _json_error(503, "hermes_disabled", "Hermes mode not active")

    async with async_session_factory() as session:
        tenant_id = await _get_tenant_id(subscription_service, session, user_id)

    if not tenant_id:
        return _json_error(404, "no_active_subscription", "No active subscription")

    return panel_service, tenant_id


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


# ============================================
# Restart
# ============================================


async def tenant_restart_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    ok = await panel_service.restart_tenant(tenant_id)
    if not ok:
        return _json_error(502, "restart_failed", "Failed to queue restart")
    return json_response({"ok": True})


# ============================================
# Quota
# ============================================


async def tenant_quota_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    quota = await panel_service.get_tenant_quota(tenant_id)
    if quota is None:
        return _json_error(502, "quota_fetch_failed", "Failed to fetch quota")
    return json_response({"ok": True, **quota})


async def tenant_cornllm_key_route(request: web.Request) -> web.Response:
    """Return the user's CornLLM virtual key for the Settings UI.

    Exposes only the customer-scoped virtual key (one per tenant).
    Never the LiteLLM master key, never the upstream provider key.
    The Mini App renders it masked by default; the user explicitly
    reveals/copies on demand.
    """
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    payload = await panel_service.get_tenant_cornllm_key(tenant_id)
    if payload is None:
        return _json_error(404, "no_active_key", "No active CornLLM key for this tenant")
    return json_response({"ok": True, **payload})


# ============================================
# Logs
# ============================================


async def tenant_logs_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    logs = await panel_service.get_tenant_logs(tenant_id)
    return json_response({"ok": True, "logs": logs})


async def tenant_logs_refresh_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    ok = await panel_service.refresh_tenant_logs(tenant_id)
    if not ok:
        return _json_error(502, "logs_refresh_failed", "Failed to refresh logs")
    return json_response({"ok": True})


# ============================================
# Suspend / delete (self-service)
# ============================================


async def tenant_suspend_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    ok = await panel_service.update_user_status_on_panel(tenant_id, enable=False)
    if not ok:
        return _json_error(502, "suspend_failed", "Failed to suspend tenant")
    return json_response({"ok": True})


async def tenant_pause_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    ok = await panel_service.pause_tenant(tenant_id)
    if not ok:
        return _json_error(502, "pause_failed", "Failed to pause tenant")
    return json_response({"ok": True, "status": "paused"})


async def tenant_start_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    ok = await panel_service.update_user_status_on_panel(tenant_id, enable=True)
    if not ok:
        return _json_error(502, "start_failed", "Failed to start tenant")
    return json_response({"ok": True, "status": "active"})


async def tenant_delete_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    ok = await panel_service.delete_user_from_panel(tenant_id)
    if not ok:
        return _json_error(502, "delete_failed", "Failed to delete tenant")
    return json_response({"ok": True})


# ponytail: the user-facing "Создать нового бота" flow re-runs
# create_panel_user with the stored bot_token. The core's create
# endpoint detects the existing row in (deleting / deleted / archived)
# state, resurrects it in place and enqueues the create jobs. This
# is separate from activate_trial_subscription which is blocked
# when the user already has an active subscription.
async def tenant_recreate_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    async_session_factory: sessionmaker = get_session_factory(request)
    subscription_service: SubscriptionService = get_subscription_service(request)

    panel_service = getattr(subscription_service, "panel_service", None)
    if panel_service is None or not isinstance(panel_service, HermesProvisioningService):
        return _json_error(503, "hermes_disabled", "Hermes mode not active")

    from db.dal import user_dal

    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or not db_user.panel_user_uuid or not db_user.pending_bot_token:
            i18n_instance = get_i18n(request) or get_i18n_instance()
            user_lang = getattr(db_user, "language_code", None) if db_user else None
            lang = user_lang or "ru"
            token_message = i18n_instance.gettext(lang, "tg_no_bot_token_error")
            return _json_error(
                400,
                "no_tenant_or_token",
                token_message,
            )
        panel_user_uuid = str(db_user.panel_user_uuid)
        bot_token = str(db_user.pending_bot_token)
        bot_username = str(getattr(db_user, "pending_bot_username", "") or "")
        telegram_id = int(db_user.telegram_id or 0)

    username_on_panel = f"tg_{telegram_id}" if telegram_id else f"hermes-{panel_user_uuid[:8]}"
    result = await panel_service.create_panel_user(
        username_on_panel=username_on_panel,
        telegram_id=telegram_id,
        bot_token=bot_token,
        bot_username=bot_username or None,
    )
    if not result or result.get("error"):
        return _json_error(502, "recreate_failed", "Failed to re-create bot on provisioning core")
    return json_response({"ok": True})


async def tenant_backup_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    data = await panel_service.backup_tenant(tenant_id)
    if not data:
        return _json_error(502, "backup_failed", "Failed to queue backup")
    return json_response({"ok": True, "job_id": data.get("job_id", "")})


async def tenant_restore_route(request: web.Request) -> web.Response:
    result = await _resolve_tenant(request)
    if isinstance(result, web.Response):
        return result
    panel_service, tenant_id = result
    body = await request.read()
    if len(body) > 50_000_000:
        return _json_error(413, "file_too_large", "Max 50MB")
    if len(body) < 100:
        return _json_error(400, "file_empty", "File too small")
    data = await panel_service.restore_tenant(tenant_id, bytes(body), "restore.zip")
    if not data:
        return _json_error(502, "restore_failed", "Failed to queue restore")
    return json_response({"ok": True, "job_id": data.get("job_id", "")})
