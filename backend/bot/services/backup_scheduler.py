"""Stream H: daily tenant backup scheduler.

Runs once per day at 04:00 MSK (01:00 UTC) and enqueues a backup job for
every active Hermes subscription via provisioning-core. The provisioner
zips tenant data and ships it to the owner via the tenant's own bot;
this worker only enqueues, it never touches zip bytes itself.

Distinct from ``bot.services.backup_worker.BackupWorker`` — that one
backs up the MINISHOP database itself (postgres + compose), unrelated to
tenants. Two different concerns, two different workers.

Runs inside the worker process (see ``main_worker._core_worker_tasks``).
Polls the wall clock every minute; the once-per-day guard avoids
re-firing on long ticks.
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
from db.models import Subscription

log = logging.getLogger(__name__)

# 04:00 MSK = 01:00 UTC. Off-peak for provisioning-core; tenants get
# fresh backups before the working day starts.
BACKUP_HOUR_UTC = 1
TICK_SECONDS = 60
# Stagger between tenants so provisioning-core doesn't see a burst of N
# simultaneous /backup POSTs when the worker has hundreds of subs.
INTER_TENANT_STAGGER_SECONDS = 30


async def daily_backup_worker(ctx: PluginContext) -> None:
    """WorkerTaskSpec entry. Infinite loop, runs once per UTC day at
    ``BACKUP_HOUR_UTC``. Exits cleanly if no ``HermesProvisioningService``
    is registered (non-hermes deployment).
    """
    panel_service: Optional[HermesProvisioningService] = None
    for svc in getattr(ctx, "services", {}).values():
        if isinstance(svc, HermesProvisioningService):
            panel_service = svc
            break
    if panel_service is None:
        log.info("backup_worker_no_hermes_service_exiting")
        return

    session_factory: sessionmaker = ctx.require_session_factory()
    log.info(
        "backup_worker_started hour_utc=%d stagger_s=%d tick_s=%d",
        BACKUP_HOUR_UTC,
        INTER_TENANT_STAGGER_SECONDS,
        TICK_SECONDS,
    )

    last_run_date: Optional[datetime] = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            # ponytail: guard on date, not datetime, so a slow tick that
            # crosses midnight still fires once and not twice.
            if now.hour == BACKUP_HOUR_UTC and (
                last_run_date is None or last_run_date.date() != now.date()
            ):
                last_run_date = now
                await _tick_once(session_factory, panel_service)
        except asyncio.CancelledError:
            log.info("backup_worker_stopped")
            raise
        except Exception:
            # ponytail: a single bad tick must not kill the worker loop.
            log.exception("backup_worker_tick_failed")
        await asyncio.sleep(TICK_SECONDS)


async def _tick_once(
    session_factory: sessionmaker,
    panel_service: HermesProvisioningService,
) -> int:
    """One pass: enqueue backup jobs for every active hermes subscription.

    Returns the number of successfully enqueued jobs. Per-tenant failures
    are logged and skipped — one bad tenant must not block the others.
    """
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Subscription).where(
                    Subscription.is_active.is_(True),
                    Subscription.panel_user_uuid.is_not(None),
                )
            )
        ).scalars().all()

    enqueued = 0
    for sub in rows:
        tenant_id = sub.panel_user_uuid
        if not tenant_id:
            continue
        sub_id = sub.subscription_id
        try:
            result = await panel_service.backup_tenant(str(tenant_id))
        except Exception:
            log.exception(
                "backup_exception subscription_id=%s tenant_id=%s", sub_id, tenant_id
            )
            await asyncio.sleep(INTER_TENANT_STAGGER_SECONDS)
            continue
        if result:
            enqueued += 1
            log.info(
                "backup_triggered subscription_id=%s tenant_id=%s job_id=%s",
                sub_id,
                tenant_id,
                result.get("job_id"),
            )
        else:
            log.warning(
                "backup_failed subscription_id=%s tenant_id=%s",
                sub_id,
                tenant_id,
            )
        await asyncio.sleep(INTER_TENANT_STAGGER_SECONDS)

    log.info(
        "backup_batch_done total=%d enqueued=%d failed=%d",
        len(rows),
        enqueued,
        len(rows) - enqueued,
    )
    return enqueued