"""Stream G.20: tenant lifecycle automation (auto-suspend expired subs).

Polls active subscriptions with ``end_date < now`` and calls the existing
suspend path (``HermesProvisioningService.update_user_status_on_panel(enable=False)``
→ POST ``/shop/tenants/{id}/suspend``). The provisioning-core suspend handler
then stops the container + revokes the LiteLLM key + freezes
``cornllm_balances`` (G.19.2). Manual suspend (Mini App button) and this
auto-suspend both write the same ``tenants.last_state_change`` on the core
side, so the same 7-day countdown (Stream G.20 — provisioning-core
``auto_delete_expired_suspensions`` task) covers both.

The 7-day auto-delete lives in provisioning-core because it touches the
``tenants`` table state directly. This worker only mirrors the local
``subscriptions.is_active = False`` flag for bookkeeping; the source of
truth for lifecycle status is ``tenants.status`` on the core side.

Run inside the worker process (see ``main_worker._core_worker_tasks``).
Tick interval defaults to 60 seconds.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bot.plugins.spec import PluginContext
from bot.services.hermes_provisioning_service import HermesProvisioningService
from config.settings import Settings, get_settings
from db.models import Subscription

log = logging.getLogger(__name__)


async def auto_suspend_expired_subscriptions_worker(ctx: PluginContext) -> None:
    """WorkerTaskSpec entry. Infinite loop, calls ``_tick_once`` every
    ``AUTO_SUSPEND_CHECK_INTERVAL_SECONDS``. Exits cleanly if no
    ``HermesProvisioningService`` is registered (non-hermes deployment).
    """
    settings = get_settings()
    if not settings.AUTO_SUSPEND_ENABLED:
        log.info("auto_suspend_disabled_exiting")
        return

    panel_service: Optional[HermesProvisioningService] = None
    for svc in getattr(ctx, "services", {}).values():
        if isinstance(svc, HermesProvisioningService):
            panel_service = svc
            break
    if panel_service is None:
        log.info("auto_suspend_no_hermes_service_exiting")
        return

    session_factory: sessionmaker = ctx.require_session_factory()
    interval = settings.AUTO_SUSPEND_CHECK_INTERVAL_SECONDS
    log.info("auto_suspend_worker_started interval=%d", interval)

    while True:
        try:
            await _tick_once(session_factory, panel_service)
        except asyncio.CancelledError:
            log.info("auto_suspend_worker_stopped")
            raise
        except Exception:
            # ponytail: a single tick failure must not kill the worker.
            log.exception("auto_suspend_worker_tick_failed")
        await asyncio.sleep(interval)


async def _tick_once(
    session_factory: sessionmaker,
    panel_service: HermesProvisioningService,
    *,
    now: Optional[datetime] = None,
    settings: Optional[Settings] = None,
) -> int:
    """One pass over due (expired) subscriptions. Returns count suspended.

    Split from the loop so tests can call this directly with a fake
    sessionmaker + panel_service without driving the infinite loop.
    ``now`` and ``settings`` are injectable for deterministic tests.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if settings is None:
        settings = get_settings()
    suspended = 0
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Subscription).where(
                    Subscription.is_active.is_(True),
                    Subscription.end_date.is_not(None),
                    Subscription.end_date < now,
                    Subscription.panel_user_uuid.is_not(None),
                )
            )
        ).scalars().all()

        for sub in rows:
            panel_uuid = sub.panel_user_uuid
            if not panel_uuid:
                continue
            sub_id = getattr(sub, "subscription_id", None) or getattr(sub, "id", None)
            try:
                ok = await panel_service.update_user_status_on_panel(
                    panel_uuid, enable=False
                )
            except Exception:
                # ponytail: a single bad call must not break the tick —
                # other expired subs still need to be processed.
                log.exception(
                    "auto_suspend_exception subscription_id=%s",
                    sub_id,
                )
                continue

            if not ok:
                log.warning(
                    "auto_suspend_failed subscription_id=%s panel_uuid=%s",
                    sub_id,
                    panel_uuid,
                )
                continue

            # provisioning-core's tenants.status is the source of truth;
            # flip the local mirror so subsequent queries don't see it
            # as a still-active sub (avoids re-firing the suspend on
            # the next tick — provisioning-core would 409 the duplicate).
            sub.is_active = False
            suspended += 1
            log.info(
                "auto_suspend_fired subscription_id=%s panel_uuid=%s end_date=%s",
                sub_id,
                panel_uuid,
                sub.end_date,
            )

        await session.commit()
    return suspended