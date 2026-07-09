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
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional, TypeAlias, assert_never

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bot.plugins.spec import PluginContext
from bot.services.hermes_provisioning_service import HermesProvisioningService
from bot.utils.mini_app_url import subscription_mini_app_renew_url
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


async def deletion_warning_notifications_worker(ctx: PluginContext) -> None:
    """Stream G.24: T-1d / T-1h Telegram warnings before auto-delete."""
    settings = get_settings()
    panel_service: Optional[HermesProvisioningService] = None
    for svc in getattr(ctx, "services", {}).values():
        if isinstance(svc, HermesProvisioningService):
            panel_service = svc
            break
    if panel_service is None:
        log.info("deletion_warning_no_hermes_service_exiting")
        return

    bot = ctx.require_bot()
    session_factory: sessionmaker = ctx.require_session_factory()
    interval = settings.DELETION_WARNING_CHECK_INTERVAL_SECONDS
    sweep_days = settings.AUTO_DELETE_AFTER_SUSPENSION_DAYS
    t1d_h = settings.DELETION_WARNING_HOURS_BEFORE
    t1h_h = settings.DELETION_CRITICAL_WARNING_HOURS_BEFORE

    log.info(
        "deletion_warning_worker_started interval=%d sweep_days=%d t1d=%dh t1h=%dh",
        interval,
        sweep_days,
        t1d_h,
        t1h_h,
    )

    while True:
        try:
            await _deletion_warning_tick_once(
                session_factory,
                panel_service,
                bot,
                sweep_days=sweep_days,
                t1d_h=t1d_h,
                t1h_h=t1h_h,
            )
        except asyncio.CancelledError:
            log.info("deletion_warning_worker_stopped")
            raise
        except Exception:
            log.exception("deletion_warning_worker_tick_failed")
        await asyncio.sleep(interval)


async def _deletion_warning_tick_once(
    session_factory: sessionmaker,
    panel_service: HermesProvisioningService,
    bot: Bot,
    *,
    sweep_days: int,
    t1d_h: int,
    t1h_h: int,
    now: Optional[datetime] = None,
) -> int:
    """One pass over suspended subscriptions approaching auto-delete."""
    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = _as_utc_datetime(now) or now
    sent = 0
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Subscription).where(
                    Subscription.is_active.is_(False),
                    Subscription.panel_user_uuid.is_not(None),
                )
            )
        ).scalars().all()

        for sub in rows:
            panel_uuid = sub.panel_user_uuid
            if not panel_uuid:
                continue
            try:
                tenant_state = await panel_service.get_tenant_state(str(panel_uuid))
            except Exception:
                log.exception(
                    "deletion_warning_state_lookup_failed panel_uuid=%s",
                    panel_uuid,
                )
                continue
            if not tenant_state or tenant_state.get("status") != "suspended":
                continue

            suspended_at = _as_utc_datetime(tenant_state.get("last_state_change"))
            if suspended_at is None:
                continue

            deletion_at = suspended_at + timedelta(days=sweep_days)
            time_left = deletion_at - now

            if (
                time_left <= timedelta(hours=t1d_h)
                and time_left > timedelta(hours=t1h_h)
                and sub.deletion_warned_at is None
            ):
                ok = await _send_deletion_warning(
                    bot,
                    sub,
                    level="warning",
                    deletion_at=deletion_at,
                )
                if ok:
                    sub.deletion_warned_at = now
                    sent += 1
            elif (
                time_left <= timedelta(hours=t1h_h)
                and time_left > timedelta(seconds=0)
                and sub.deletion_critical_warned_at is None
            ):
                ok = await _send_deletion_warning(
                    bot,
                    sub,
                    level="critical",
                    deletion_at=deletion_at,
                )
                if ok:
                    sub.deletion_critical_warned_at = now
                    sent += 1

        await session.commit()
    return sent


def _as_utc_datetime(value: datetime | str | None) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            log.warning("deletion_warning_invalid_last_state_change value=%s", raw)
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


DeletionWarningLevel: TypeAlias = Literal["warning", "critical"]


async def _send_deletion_warning(
    bot: Bot,
    sub: Subscription,
    *,
    level: DeletionWarningLevel,
    deletion_at: datetime,
) -> bool:
    """Send one Telegram deletion-warning message."""
    settings = get_settings()
    user_id = int(sub.user_id)
    deletion_str = deletion_at.strftime("%d.%m %H:%M UTC")
    # TODO: migrate _send_deletion_warning to use t() with deletion.* i18n keys.
    match level:
        case "warning":
            text = (
                f"⚠️ <b>Ваш контейнер будет удалён {deletion_str}</b>\n\n"
                "Все данные (настройки Hermes, история чатов) будут потеряны.\n\n"
                "Чтобы сохранить — продлите подписку сейчас."
            )
        case "critical":
            text = (
                "🚨 <b>Последний шанс!</b>\n\n"
                "Контейнер удалится через час. Восстановление после удаления невозможно."
            )
        case unreachable:
            assert_never(unreachable)

    renew_url = subscription_mini_app_renew_url(settings, getattr(sub, "tariff_key", None))
    keyboard = (
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💳 Продлить",
                        web_app=WebAppInfo(url=renew_url),
                    )
                ]
            ]
        )
        if renew_url
        else None
    )
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return True
    except Exception:
        log.warning(
            "deletion_warning_send_failed user_id=%s level=%s",
            user_id,
            level,
        )
        return False
