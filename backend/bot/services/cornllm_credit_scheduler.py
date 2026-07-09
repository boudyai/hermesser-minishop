"""Stream G.11 — monthly CornLLM sub-credit grant scheduler.

Polls subscriptions where ``next_credit_at <= now`` AND ``is_active=True``
AND ``next_credit_amount_usd IS NOT NULL``, calls
``HermesProvisioningService.grant_subscription_quota`` on the tenant's
panel UUID, then bumps ``next_credit_at += 30 days`` (or NULL when the
next bump would exceed ``end_date``).

Single-grant subscriptions (trial, 1-month sub, zero-credit tariff) have
``next_credit_at = NULL`` and are naturally skipped by the WHERE filter.

Idempotent: after firing a grant, ``next_credit_at`` is updated to a
future time (or NULL), so the same subscription won't be picked up again
on the next tick. If the scheduler crashes mid-batch, the next tick
resumes from the unprocessed rows — only fully committed bumps are
removed from the working set.

Run inside the worker process (see ``main_worker._core_worker_tasks``).
Tick interval defaults to 60 seconds.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bot.services.hermes_provisioning_service import HermesProvisioningService
from db.models import Subscription

if TYPE_CHECKING:
    from bot.plugins.spec import PluginContext

log = logging.getLogger(__name__)


# ponytail: tick interval. 60s is responsive enough for monthly scheduling
# without hammering the DB. Fixed 30-day month per G.9 / G.11 design.
CORNLLM_GRANT_TICK_SECONDS = 60
MONTH_DAYS = 30


async def cornllm_monthly_grant_worker(ctx: "PluginContext") -> None:
    """Infinite-loop worker that fires monthly sub-credit grants.

    Locates the HermesProvisioningService in ``ctx.services``; if it isn't
    registered (non-hermes deployment), the worker exits immediately —
    there is nothing to grant.
    """
    panel_service: Optional[HermesProvisioningService] = None
    # ponytail: scan ctx.services for the hermes-mode panel service instead
    # of relying on a fixed key, matching how SubscriptionNotificationWorker
    # gates hermes-specific behaviour.
    for svc in getattr(ctx, "services", {}).values():
        if isinstance(svc, HermesProvisioningService):
            panel_service = svc
            break
    if panel_service is None:
        log.info("cornllm_grant_worker_no_hermes_service_exiting")
        return

    session_factory: sessionmaker = ctx.require_session_factory()
    log.info(
        "cornllm_grant_worker_started tick_seconds=%d", CORNLLM_GRANT_TICK_SECONDS
    )

    while True:
        try:
            await _tick_once(session_factory, panel_service)
        except asyncio.CancelledError:
            log.info("cornllm_grant_worker_stopped")
            raise
        except Exception:
            # ponytail: a single tick failure must not kill the worker.
            log.exception("cornllm_grant_worker_tick_failed")
        await asyncio.sleep(CORNLLM_GRANT_TICK_SECONDS)


async def _tick_once(
    session_factory: sessionmaker,
    panel_service: HermesProvisioningService,
    *,
    now: Optional[datetime] = None,
) -> int:
    """One pass over due subscriptions. Returns the count of grants fired.

    Split from the loop so tests can call this directly with a fake
    sessionmaker + panel_service without driving the infinite loop.
    ``now`` is injectable for deterministic tests.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    fired = 0
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Subscription).where(
                    Subscription.is_active.is_(True),
                    Subscription.next_credit_at.is_not(None),
                    Subscription.next_credit_at <= now,
                    Subscription.next_credit_amount_usd.is_not(None),
                )
            )
        ).scalars().all()

        for sub in rows:
            # ponytail: defence-in-depth — the SQL WHERE filter excludes
            # NULL next_credit_at / next_credit_amount_usd, but a buggy
            # query or data drift could leak one through. Skip silently
            # here so the bump arithmetic never crashes on None.
            if sub.next_credit_at is None or sub.next_credit_amount_usd is None:
                log.warning(
                    "cornllm_grant_skip_unset_schedule subscription_id=%s",
                    getattr(sub, "subscription_id", None),
                )
                continue

            panel_user_uuid = getattr(sub, "panel_user_uuid", None)
            if not panel_user_uuid:
                log.warning(
                    "cornllm_grant_skip_no_panel_uuid subscription_id=%s",
                    getattr(sub, "subscription_id", None),
                )
                continue

            amount = float(sub.next_credit_amount_usd or 0.0)
            try:
                result = await panel_service.grant_subscription_quota(
                    str(panel_user_uuid), amount
                )
            except Exception:
                # ponytail: an exception from one subscription must not
                # abort the rest of the batch — log and move on.
                log.exception(
                    "cornllm_grant_exception subscription_id=%s",
                    getattr(sub, "subscription_id", None),
                )
                continue

            if not result:
                log.warning(
                    "cornllm_grant_failed subscription_id=%s amount=%.4f",
                    getattr(sub, "subscription_id", None),
                    amount,
                )
                # Don't bump next_credit_at on failure — the next tick
                # retries. Server-side override is idempotent on amount.
                continue

            # next_credit_at is non-None here — guarded above and by the
            # SQL WHERE filter; the cast is for mypy only.
            assert sub.next_credit_at is not None
            next_at = sub.next_credit_at + timedelta(days=MONTH_DAYS)
            end_date = getattr(sub, "end_date", None)
            if end_date is not None and next_at >= end_date:
                sub.next_credit_at = None
                sub.next_credit_amount_usd = None
                log.info(
                    "cornllm_grant_final subscription_id=%s amount=%.4f end_date=%s",
                    getattr(sub, "subscription_id", None),
                    amount,
                    end_date,
                )
            else:
                sub.next_credit_at = next_at
                log.info(
                    "cornllm_grant_fired subscription_id=%s amount=%.4f next_at=%s",
                    getattr(sub, "subscription_id", None),
                    amount,
                    next_at,
                )
            fired += 1

        await session.commit()
    return fired