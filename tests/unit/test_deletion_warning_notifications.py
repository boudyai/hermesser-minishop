from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, patch

import bot.app.web.subscription_webapp  # noqa: F401
from bot.services.hermes_provisioning_service import HermesProvisioningService
from bot.services.tenant_lifecycle_scheduler import _deletion_warning_tick_once
from config.settings import Settings


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class FakeAsyncSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.committed = False
        self.executed = 0

    async def __aenter__(self) -> FakeAsyncSession:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    async def execute(self, statement: Any) -> _FakeResult:
        self.executed += 1
        return _FakeResult(self._rows)

    async def commit(self) -> None:
        self.committed = True


class FakeSessionFactory:
    def __init__(self, rows: list[Any]) -> None:
        self.session = FakeAsyncSession(rows)

    def __call__(self) -> FakeAsyncSession:
        return self.session


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        BOT_TOKEN="t",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        PANEL_API_URL="http://core:9999",
        PANEL_API_KEY="test-key",
        SUBSCRIPTION_MINI_APP_URL="https://app.example.com",
    )


def _make_panel_service(
    *,
    state: Optional[dict[str, Any]] = None,
    side_effect: Optional[Any] = None,
) -> HermesProvisioningService:
    service = HermesProvisioningService(_settings())
    if side_effect is not None:
        service.get_tenant_state = AsyncMock(side_effect=side_effect)
    else:
        service.get_tenant_state = AsyncMock(return_value=state)
    return service


def _make_sub(
    *,
    subscription_id: int = 1,
    user_id: int = 1001,
    panel_user_uuid: Optional[str] = "tenant-1",
    deletion_warned_at: Optional[datetime] = None,
    deletion_critical_warned_at: Optional[datetime] = None,
) -> Any:
    return SimpleNamespace(
        subscription_id=subscription_id,
        user_id=user_id,
        panel_user_uuid=panel_user_uuid,
        deletion_warned_at=deletion_warned_at,
        deletion_critical_warned_at=deletion_critical_warned_at,
        tariff_key="standard",
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _run_tick(
    rows: list[Any],
    panel_service: HermesProvisioningService,
    bot: Any,
    *,
    now: datetime,
) -> int:
    factory = FakeSessionFactory(rows)
    with patch("bot.services.tenant_lifecycle_scheduler.get_settings", return_value=_settings()):
        return int(
            _run(
                _deletion_warning_tick_once(
                    factory,
                    panel_service,
                    bot,
                    sweep_days=7,
                    t1d_h=24,
                    t1h_h=1,
                    now=now,
                )
            )
        )


def test_no_subscriptions_returns_zero() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    bot = AsyncMock()
    panel_service = _make_panel_service(state=None)

    sent = _run_tick([], panel_service, bot, now=now)

    assert sent == 0
    panel_service.get_tenant_state.assert_not_awaited()
    bot.send_message.assert_not_awaited()


def test_skip_when_tenant_state_active() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub = _make_sub()
    panel_service = _make_panel_service(
        state={"status": "active", "last_state_change": now - timedelta(days=6, hours=1)}
    )
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    bot.send_message.assert_not_awaited()


def test_skip_when_tenant_state_paused() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub = _make_sub()
    panel_service = _make_panel_service(
        state={"status": "paused", "last_state_change": now - timedelta(days=6, hours=1)}
    )
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    bot.send_message.assert_not_awaited()


def test_skip_when_no_last_state_change() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub = _make_sub()
    panel_service = _make_panel_service(state={"status": "suspended"})
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    bot.send_message.assert_not_awaited()


def test_t1d_warning_fires_24h_before_deletion() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    suspended_at = now - timedelta(days=6, hours=1)
    sub = _make_sub()
    panel_service = _make_panel_service(
        state={"status": "suspended", "last_state_change": suspended_at}
    )
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 1
    bot.send_message.assert_awaited_once()
    assert sub.deletion_warned_at == now
    assert sub.deletion_critical_warned_at is None


def test_t1h_warning_fires_1h_before_deletion() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    suspended_at = now - timedelta(days=6, hours=23)
    sub = _make_sub()
    panel_service = _make_panel_service(
        state={"status": "suspended", "last_state_change": suspended_at}
    )
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 1
    bot.send_message.assert_awaited_once()
    assert sub.deletion_warned_at is None
    assert sub.deletion_critical_warned_at == now


def test_no_double_warning_after_t1d_fired() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    already_warned = now - timedelta(hours=2)
    sub = _make_sub(deletion_warned_at=already_warned)
    panel_service = _make_panel_service(
        state={"status": "suspended", "last_state_change": now - timedelta(days=6, hours=1)}
    )
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    bot.send_message.assert_not_awaited()
    assert sub.deletion_warned_at == already_warned


def test_t1d_skipped_when_time_left_too_far() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub = _make_sub()
    panel_service = _make_panel_service(
        state={"status": "suspended", "last_state_change": now - timedelta(days=3)}
    )
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    bot.send_message.assert_not_awaited()
    assert sub.deletion_warned_at is None


def test_t1h_skipped_when_time_left_too_far() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub = _make_sub(deletion_warned_at=now - timedelta(hours=3))
    panel_service = _make_panel_service(
        state={"status": "suspended", "last_state_change": now - timedelta(days=6, hours=22)}
    )
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    bot.send_message.assert_not_awaited()
    assert sub.deletion_critical_warned_at is None


def test_send_failure_does_not_stamp_marker() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub = _make_sub()
    panel_service = _make_panel_service(
        state={"status": "suspended", "last_state_change": now - timedelta(days=6, hours=1)}
    )
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("blocked"))

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    bot.send_message.assert_awaited_once()
    assert sub.deletion_warned_at is None
    assert sub.deletion_critical_warned_at is None


def test_skip_subscription_without_panel_uuid() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub = _make_sub(panel_user_uuid=None)
    panel_service = _make_panel_service(state=None)
    bot = AsyncMock()

    sent = _run_tick([sub], panel_service, bot, now=now)

    assert sent == 0
    panel_service.get_tenant_state.assert_not_awaited()
    bot.send_message.assert_not_awaited()


def test_tick_continues_on_panel_lookup_exception() -> None:
    now = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    sub_a = _make_sub(subscription_id=1, panel_user_uuid="tenant-a")
    sub_b = _make_sub(subscription_id=2, panel_user_uuid="tenant-b")
    panel_service = _make_panel_service(
        side_effect=[
            RuntimeError("core down"),
            {"status": "suspended", "last_state_change": now - timedelta(days=6, hours=1)},
        ]
    )
    bot = AsyncMock()

    sent = _run_tick([sub_a, sub_b], panel_service, bot, now=now)

    assert sent == 1
    assert panel_service.get_tenant_state.await_count == 2
    bot.send_message.assert_awaited_once()
    assert sub_a.deletion_warned_at is None
    assert sub_b.deletion_warned_at == now
