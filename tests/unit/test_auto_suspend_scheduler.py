"""Tests for the auto-suspend-expired-subscriptions worker (Stream G.20).

Pins the WHERE-filter behaviour (active + end_date past + panel_user_uuid
present), the panel-service call signature, the local ``is_active``
bookkeeping flip, and the worker-level exit conditions (kill switch,
missing HermesProvisioningService).

The sessionmaker is replaced with the same ``FakeSessionFactory`` shape
used by ``test_cornllm_credit_scheduler.py`` — pre-built row list
returned from ``execute()``, recorded commits, no real SQL. The panel
service is a real ``HermesProvisioningService`` with
``update_user_status_on_panel`` patched via ``AsyncMock`` so mypy stays
strict-clean.

Worker exit tests use ``asyncio.wait_for`` with a small timeout: the
worker is supposed to return immediately on kill-switch / missing
service, not enter its infinite loop. If the worker falls through to
the loop, ``wait_for`` raises ``TimeoutError`` and the test fails.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import AsyncMock

import bot.app.web.subscription_webapp  # noqa: F401 — populates _runtime
from bot.plugins.spec import PluginContext
from bot.services.hermes_provisioning_service import HermesProvisioningService
from bot.services.tenant_lifecycle_scheduler import (
    _tick_once,
    auto_suspend_expired_subscriptions_worker,
)
from config.settings import Settings, get_settings

# ============================================
# Fakes
# ============================================


class _FakeScalars:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def all(self) -> List[Any]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class FakeAsyncSession:
    """Async-session fake used by ``FakeSessionFactory``.

    Returns a pre-built row list from every ``execute()`` call and
    records commit() invocations so tests can verify the tick commits
    at the end.
    """

    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows
        self.committed = False
        self.executed = 0

    async def __aenter__(self) -> "FakeAsyncSession":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    async def execute(self, statement: Any) -> _FakeResult:
        self.executed += 1
        return _FakeResult(self._rows)

    async def commit(self) -> None:
        self.committed = True


class FakeSessionFactory:
    """``sessionmaker``-shaped callable that yields a single FakeAsyncSession."""

    def __init__(self, rows: List[Any]) -> None:
        self.session = FakeAsyncSession(rows)

    def __call__(self) -> FakeAsyncSession:
        return self.session


# ============================================
# Helpers
# ============================================


def _make_sub(
    *,
    subscription_id: int = 1,
    panel_user_uuid: Optional[str] = "panel-uuid-1",
    is_active: bool = True,
    end_date: Optional[datetime] = None,
) -> Any:
    return SimpleNamespace(
        subscription_id=subscription_id,
        panel_user_uuid=panel_user_uuid,
        is_active=is_active,
        end_date=end_date if end_date is not None else datetime(2099, 1, 1, tzinfo=timezone.utc),
    )


def _make_panel_service(
    *,
    suspend_result: Optional[bool] = None,
    suspend_side_effect: Optional[Any] = None,
) -> HermesProvisioningService:
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="t",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        PANEL_API_URL="http://core:9999",
        PANEL_API_KEY="test-key",
    )
    service = HermesProvisioningService(settings)
    if suspend_side_effect is not None:
        service.update_user_status_on_panel = AsyncMock(side_effect=suspend_side_effect)
    else:
        service.update_user_status_on_panel = AsyncMock(return_value=suspend_result)
    return service


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _settings(**overrides: Any) -> Settings:
    """Build a Settings with AUTO_SUSPEND overrides for worker-exit tests."""
    return Settings(
        _env_file=None,
        BOT_TOKEN="t",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        PANEL_API_URL="http://core:9999",
        PANEL_API_KEY="test-key",
        **overrides,
    )


def _make_ctx(
    settings: Settings,
    *,
    panel_service: Optional[HermesProvisioningService] = None,
    session_factory: Optional[FakeSessionFactory] = None,
) -> PluginContext:
    """Build a PluginContext stub for worker-exit tests.

    services is a flat dict keyed by object id-ish names; the worker
    scans with isinstance, so the panel service only needs to be in
    the dict to be discovered.
    """
    services: dict[str, Any] = {}
    if panel_service is not None:
        services["hermes"] = panel_service
    sf = session_factory or FakeSessionFactory([])
    ctx = PluginContext(settings=settings, session_factory=sf, services=services)
    return ctx


# ============================================
# _tick_once — success / filter tests
# ============================================


class TestTickOnceFiresDue:
    def test_suspends_expired_active_subscription_and_flips_is_active(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        end_date = now - timedelta(hours=25)  # past 24h grace
        sub = _make_sub(
            subscription_id=42,
            panel_user_uuid="panel-uuid-42",
            is_active=True,
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(suspend_result=True)
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, now=now, settings=settings))

        assert suspended == 1
        panel_service.update_user_status_on_panel.assert_awaited_once_with(
            "panel-uuid-42", enable=False
        )
        # Local mirror flipped; provisioning-core is the source of truth.
        assert sub.is_active is False
        assert factory.session.committed is True

    def test_returns_zero_and_skips_when_no_subs(self) -> None:
        factory = FakeSessionFactory([])
        panel_service = _make_panel_service(suspend_result=True)
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, settings=settings))

        assert suspended == 0
        panel_service.update_user_status_on_panel.assert_not_awaited()
        assert factory.session.committed is True


class TestTickOnceFilters:
    def test_skips_active_subscription_with_future_end_date(self) -> None:
        # Same modelling as the cornllm_credit_scheduler tests: production
        # filters at SQL level (end_date < now), so a future row never
        # reaches _tick_once. Pin by passing an empty list.
        factory = FakeSessionFactory([])
        panel_service = _make_panel_service(suspend_result=True)
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, settings=settings))

        assert suspended == 0
        panel_service.update_user_status_on_panel.assert_not_awaited()

    def test_skips_inactive_subscription(self) -> None:
        # Production SQL filter pins is_active=TRUE; an already-inactive
        # row never reaches _tick_once. Pin with an empty list.
        factory = FakeSessionFactory([])
        panel_service = _make_panel_service(suspend_result=True)
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, settings=settings))

        assert suspended == 0
        panel_service.update_user_status_on_panel.assert_not_awaited()

    def test_skips_subscription_within_grace_period(self) -> None:
        """Sub expired 1h ago → still within 24h grace → NOT suspended."""
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        end_date = now - timedelta(hours=1)  # within grace
        sub = _make_sub(
            subscription_id=1,
            panel_user_uuid="panel-1",
            is_active=True,
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service()
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, now=now, settings=settings))

        assert suspended == 0
        panel_service.update_user_status_on_panel.assert_not_awaited()
        assert factory.session.committed is True

    def test_skips_subscription_without_panel_uuid(self) -> None:
        # SQL filter excludes NULL panel_user_uuid, but a buggy query or
        # data drift could leak one through. The in-function guard
        # ``if not panel_uuid: continue`` should still skip it.
        sub = _make_sub(
            panel_user_uuid=None,
            end_date=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(suspend_result=True)
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, settings=settings))

        assert suspended == 0
        panel_service.update_user_status_on_panel.assert_not_awaited()


class TestTickOnceSuspendFailure:
    def test_does_not_flip_is_active_when_panel_returns_false(self) -> None:
        """When the suspend call returns False (server 5xx, 409), the
        tick should NOT flip ``is_active`` — the next tick retries. Same
        pattern as cornllm_monthly_grant_worker on grant failure."""
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        sub = _make_sub(
            panel_user_uuid="panel-uuid-1",
            end_date=now - timedelta(hours=25),
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(suspend_result=False)
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, now=now, settings=settings))

        assert suspended == 0
        panel_service.update_user_status_on_panel.assert_awaited_once_with(
            "panel-uuid-1", enable=False
        )
        # Retry on next tick — bookkeeping stays put.
        assert sub.is_active is True

    def test_continues_after_exception_and_does_not_flip(self) -> None:
        """An exception from update_user_status_on_panel on sub A must
        not stop sub B from being processed. Mirrors cornllm_credit_scheduler."""
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        end_date = now - timedelta(hours=25)
        sub_a = _make_sub(
            subscription_id=1,
            panel_user_uuid="panel-A",
            end_date=end_date,
        )
        sub_b = _make_sub(
            subscription_id=2,
            panel_user_uuid="panel-B",
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub_a, sub_b])
        # First call raises, second returns True — sub A fails, sub B fires.
        panel_service = _make_panel_service(
            suspend_side_effect=[RuntimeError("core down"), True]
        )
        settings = _settings()

        suspended = _run(_tick_once(factory, panel_service, now=now, settings=settings))

        assert suspended == 1
        assert panel_service.update_user_status_on_panel.await_count == 2
        # Sub A: not flipped (will retry next tick).
        assert sub_a.is_active is True
        # Sub B: flipped (success).
        assert sub_b.is_active is False
        # The tick still commits despite the exception.
        assert factory.session.committed is True


# ============================================
# Worker-level exit conditions
# ============================================


class TestWorkerExits:
    def test_worker_exits_when_auto_suspend_disabled(self) -> None:
        """Kill switch: AUTO_SUSPEND_ENABLED=False → worker returns
        immediately without entering the loop."""
        settings = _settings(AUTO_SUSPEND_ENABLED=False)
        # Note: panel_service + session_factory are irrelevant here —
        # the worker returns before touching them.
        ctx = _make_ctx(settings)

        # If the worker enters its loop, asyncio.wait_for will time out.
        # Use a generous timeout (1s) — the worker should return in ms.
        _run(asyncio.wait_for(auto_suspend_expired_subscriptions_worker(ctx), timeout=1.0))

    def test_worker_exits_when_no_hermes_service(self) -> None:
        """ctx.services has no HermesProvisioningService → worker returns
        immediately. Mirrors cornllm_monthly_grant_worker's defensive
        check for non-hermes deployments."""
        settings = _settings()  # AUTO_SUSPEND_ENABLED=True default
        ctx = _make_ctx(settings)  # no panel_service in services

        _run(asyncio.wait_for(auto_suspend_expired_subscriptions_worker(ctx), timeout=1.0))

    def test_worker_exits_when_no_hermes_service_even_if_enabled(self) -> None:
        """Defence-in-depth: explicit AUTO_SUSPEND_ENABLED=True +
        no HermesProvisioningService → still exits (the missing-service
        guard runs after the kill-switch check)."""
        settings = _settings(AUTO_SUSPEND_ENABLED=True)
        ctx = _make_ctx(settings, panel_service=None)

        _run(asyncio.wait_for(auto_suspend_expired_subscriptions_worker(ctx), timeout=1.0))


# ============================================
# Settings — pinned so a future refactor doesn't silently change behaviour.
# ============================================


class TestSettings:
    def test_auto_suspend_defaults_match_spec(self) -> None:
        """Kill switch ON, 60s tick interval. Pinning these so a future
        config change surfaces here, not in production."""
        settings = Settings(
            _env_file=None,
            BOT_TOKEN="t",
            POSTGRES_USER="u",
            POSTGRES_PASSWORD="p",
            PANEL_API_URL="http://core:9999",
            PANEL_API_KEY="test-key",
        )
        assert settings.AUTO_SUSPEND_ENABLED is True
        assert settings.AUTO_SUSPEND_CHECK_INTERVAL_SECONDS == 60

    def test_get_settings_loads_auto_suspend_fields(self) -> None:
        """Sanity: the cached get_settings() picks up the new fields."""
        settings = get_settings()
        assert hasattr(settings, "AUTO_SUSPEND_ENABLED")
        assert hasattr(settings, "AUTO_SUSPEND_CHECK_INTERVAL_SECONDS")