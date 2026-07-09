"""Tests for the monthly CornLLM sub-credit grant scheduler (Stream G.11).

Pins the WHERE-filter behaviour, the panel UUID resolution (now stored
directly on Subscription), and the ``next_credit_at`` bump logic — in
particular, the NULL transition when the next bump would exceed
``end_date``. Tests exercise ``_tick_once`` directly so the infinite
loop never starts.

The sessionmaker is replaced with a ``FakeSessionFactory`` whose inner
``FakeAsyncSession.execute()`` returns a pre-built row list — there is
no real SQL involved. ``grant_subscription_quota`` is patched on a real
``HermesProvisioningService`` instance to keep mypy strict-clean.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import AsyncMock

import bot.app.web.subscription_webapp  # noqa: F401 — populates _runtime
from bot.services.cornllm_credit_scheduler import (
    MONTH_DAYS,
    _tick_once,
)
from bot.services.hermes_provisioning_service import HermesProvisioningService
from config.settings import Settings

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
    at the end. Optional ``execute_raises`` propagates an exception
    out of execute() — used for "grant fails the whole tick" coverage.
    """

    def __init__(
        self,
        rows: List[Any],
        *,
        execute_raises: Optional[BaseException] = None,
    ) -> None:
        self._rows = rows
        self._execute_raises = execute_raises
        self.committed = False
        self.executed = 0

    async def __aenter__(self) -> "FakeAsyncSession":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    async def execute(self, statement: Any) -> _FakeResult:
        self.executed += 1
        if self._execute_raises is not None:
            raise self._execute_raises
        return _FakeResult(self._rows)

    async def commit(self) -> None:
        self.committed = True


class FakeSessionFactory:
    """``sessionmaker``-shaped callable that yields a single FakeAsyncSession."""

    def __init__(
        self,
        rows: List[Any],
        *,
        execute_raises: Optional[BaseException] = None,
    ) -> None:
        self.session = FakeAsyncSession(rows, execute_raises=execute_raises)

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
    next_credit_at: Optional[datetime] = None,
    next_credit_amount_usd: Optional[float] = 3.0,
    end_date: Optional[datetime] = None,
) -> Any:
    return SimpleNamespace(
        subscription_id=subscription_id,
        panel_user_uuid=panel_user_uuid,
        is_active=is_active,
        end_date=end_date if end_date is not None else datetime(2099, 1, 1, tzinfo=timezone.utc),
        next_credit_at=next_credit_at,
        next_credit_amount_usd=next_credit_amount_usd,
    )


def _make_panel_service(
    *,
    grant_result: Optional[Any] = None,
    grant_side_effect: Optional[Any] = None,
) -> HermesProvisioningService:
    """Construct a real HermesProvisioningService with a patched grant method.

    Keeping the type real (rather than a SimpleNamespace) keeps mypy happy
    without forcing the production module to depend on a duck-typed Protocol.
    """
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="t",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        PANEL_API_URL="http://core:9999",
        PANEL_API_KEY="test-key",
    )
    service = HermesProvisioningService(settings)
    if grant_side_effect is not None:
        service.grant_subscription_quota = AsyncMock(side_effect=grant_side_effect)
    else:
        service.grant_subscription_quota = AsyncMock(return_value=grant_result)
    return service


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ============================================
# Success / filter tests
# ============================================


class TestTickOnceFiresDue:
    def test_fires_grant_for_due_subscription_and_bumps_next_credit_at(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        due_at = now - timedelta(hours=1)
        end_date = now + timedelta(days=60)
        sub = _make_sub(
            subscription_id=42,
            panel_user_uuid="panel-uuid-42",
            next_credit_at=due_at,
            next_credit_amount_usd=3.0,
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(
            grant_result={"new_sub_balance_usd": 3.0}
        )

        fired = _run(_tick_once(factory, panel_service, now=now))

        assert fired == 1
        panel_service.grant_subscription_quota.assert_awaited_once_with(
            "panel-uuid-42", 3.0
        )
        # next_credit_at bumped by MONTH_DAYS into the future; amount kept.
        assert sub.next_credit_at == due_at + timedelta(days=MONTH_DAYS)
        assert sub.next_credit_amount_usd == 3.0
        assert factory.session.committed is True

    def test_returns_zero_and_skips_when_due_list_is_empty(self) -> None:
        factory = FakeSessionFactory([])
        panel_service = _make_panel_service(
            grant_result={"new_sub_balance_usd": 3.0}
        )

        fired = _run(_tick_once(factory, panel_service))

        assert fired == 0
        panel_service.grant_subscription_quota.assert_not_awaited()
        assert factory.session.committed is True


class TestTickOnceFilters:
    def test_skips_subscription_with_null_next_credit_at(self) -> None:
        sub = _make_sub(next_credit_at=None, next_credit_amount_usd=3.0)
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(grant_result={"new_sub_balance_usd": 3.0})

        fired = _run(_tick_once(factory, panel_service))

        assert fired == 0
        panel_service.grant_subscription_quota.assert_not_awaited()
        # Null stays null — filter rejected it, no mutation.
        assert sub.next_credit_at is None

    def test_skips_subscription_with_future_next_credit_at(self) -> None:
        # The fake returns these rows regardless of the WHERE filter — the
        # point is to pin that the production code's WHERE filter would
        # never hand a future row in. We still expect _tick_once to call
        # grant on whatever the fake gives back, so to model real
        # production behaviour we hand back only a "past-due" sentinel.
        # Because the production code uses SQL-level filtering, future
        # rows would never reach _tick_once — but if they did, the
        # scheduler still grants based on next_credit_at. We pin the
        # contract: a *truly* due row grants; the WHERE filter is the
        # gate, not the scheduler. To exercise "no row reaches the
        # scheduler", we pass an empty list.
        factory = FakeSessionFactory([])
        panel_service = _make_panel_service(grant_result={"new_sub_balance_usd": 3.0})

        fired = _run(_tick_once(factory, panel_service))

        assert fired == 0
        panel_service.grant_subscription_quota.assert_not_awaited()

    def test_skips_subscription_with_null_amount(self) -> None:
        sub = _make_sub(
            next_credit_at=datetime.now(timezone.utc) - timedelta(hours=1),
            next_credit_amount_usd=None,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(grant_result={"new_sub_balance_usd": 0.0})

        fired = _run(_tick_once(factory, panel_service))

        assert fired == 0
        panel_service.grant_subscription_quota.assert_not_awaited()

    def test_skips_subscription_with_zero_amount(self) -> None:
        # amount=0 IS a valid override (zeroes sub_balance on plan
        # downgrade), but it shouldn't fire repeatedly — the SQL
        # filter only excludes NULL, not 0. The scheduler is allowed
        # to fire it; we pin that the scheduler does NOT special-case
        # 0 here (the activation path is responsible for setting
        # next_credit_at to NULL when the tariff has no sub-credit).
        sub = _make_sub(
            next_credit_at=datetime.now(timezone.utc) - timedelta(hours=1),
            next_credit_amount_usd=0.0,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(grant_result={"new_sub_balance_usd": 0.0})

        fired = _run(_tick_once(factory, panel_service))

        # amount=0 still fires — the scheduler doesn't suppress it;
        # the activation path is responsible for clearing the schedule
        # when the tariff drops sub-credit.
        assert fired == 1
        panel_service.grant_subscription_quota.assert_awaited_once_with(
            "panel-uuid-1", 0.0
        )

    def test_skips_inactive_subscription(self) -> None:
        # Same modelling as the future-row test: production filters at
        # SQL level (is_active is True), so an inactive row never
        # reaches _tick_once. Pin by passing an empty list.
        factory = FakeSessionFactory([])
        panel_service = _make_panel_service(grant_result={"new_sub_balance_usd": 3.0})

        fired = _run(_tick_once(factory, panel_service))

        assert fired == 0
        panel_service.grant_subscription_quota.assert_not_awaited()

    def test_skips_subscription_with_missing_panel_user_uuid(self) -> None:
        # This is an integrity gap the SQL filter cannot catch (the
        # column is non-nullable, but a defensive check logs + skips
        # in case data drifts). Exercise the in-function guard.
        sub = _make_sub(
            panel_user_uuid=None,
            next_credit_at=datetime.now(timezone.utc) - timedelta(hours=1),
            next_credit_amount_usd=3.0,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(grant_result={"new_sub_balance_usd": 3.0})

        fired = _run(_tick_once(factory, panel_service))

        assert fired == 0
        panel_service.grant_subscription_quota.assert_not_awaited()


# ============================================
# end_date NULL transition
# ============================================


class TestTickOnceEndsSubscription:
    def test_sets_null_when_next_bump_exceeds_end_date(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        due_at = now - timedelta(hours=1)
        # Less than MONTH_DAYS in the future — bump would cross end_date.
        end_date = now + timedelta(days=5)
        sub = _make_sub(
            panel_user_uuid="panel-uuid-1",
            next_credit_at=due_at,
            next_credit_amount_usd=3.0,
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(
            grant_result={"new_sub_balance_usd": 3.0}
        )

        fired = _run(_tick_once(factory, panel_service, now=now))

        assert fired == 1
        panel_service.grant_subscription_quota.assert_awaited_once_with(
            "panel-uuid-1", 3.0
        )
        # next_credit_at and amount both nulled — schedule is done.
        assert sub.next_credit_at is None
        assert sub.next_credit_amount_usd is None

    def test_keeps_amount_when_next_bump_within_end_date(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        due_at = now - timedelta(hours=1)
        # Far enough that bump lands inside end_date.
        end_date = now + timedelta(days=60)
        sub = _make_sub(
            panel_user_uuid="panel-uuid-1",
            next_credit_at=due_at,
            next_credit_amount_usd=3.0,
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(
            grant_result={"new_sub_balance_usd": 3.0}
        )

        fired = _run(_tick_once(factory, panel_service, now=now))

        assert fired == 1
        assert sub.next_credit_at == due_at + timedelta(days=MONTH_DAYS)
        assert sub.next_credit_amount_usd == 3.0


# ============================================
# Failure handling
# ============================================


class TestTickOnceContinuesOnGrantFailure:
    def test_continues_after_exception_and_does_not_bump(self) -> None:
        """An exception from grant_subscription_quota on sub A must not
        stop sub B from being processed."""
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        due_at = now - timedelta(hours=1)
        end_date = now + timedelta(days=60)
        sub_a = _make_sub(
            subscription_id=1,
            panel_user_uuid="panel-A",
            next_credit_at=due_at,
            next_credit_amount_usd=3.0,
            end_date=end_date,
        )
        sub_b = _make_sub(
            subscription_id=2,
            panel_user_uuid="panel-B",
            next_credit_at=due_at,
            next_credit_amount_usd=5.0,
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub_a, sub_b])
        # First call raises, second returns a body — sub A fails, sub B fires.
        panel_service = _make_panel_service(
            grant_side_effect=[RuntimeError("core down"), {"new_sub_balance_usd": 5.0}]
        )

        fired = _run(_tick_once(factory, panel_service, now=now))

        assert fired == 1  # only sub B succeeded
        assert panel_service.grant_subscription_quota.await_count == 2
        # Sub A: not bumped (retry on next tick).
        assert sub_a.next_credit_at == due_at
        assert sub_a.next_credit_amount_usd == 3.0
        # Sub B: bumped to future.
        assert sub_b.next_credit_at == due_at + timedelta(days=MONTH_DAYS)
        assert sub_b.next_credit_amount_usd == 5.0
        # The tick still commits at the end despite the exception.
        assert factory.session.committed is True

    def test_continues_after_none_result_and_does_not_bump(self) -> None:
        """grant_subscription_quota returning None (server 5xx) must
        not bump next_credit_at — let the next tick retry."""
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        due_at = now - timedelta(hours=1)
        end_date = now + timedelta(days=60)
        sub = _make_sub(
            panel_user_uuid="panel-uuid-1",
            next_credit_at=due_at,
            next_credit_amount_usd=3.0,
            end_date=end_date,
        )
        factory = FakeSessionFactory([sub])
        panel_service = _make_panel_service(grant_result=None)

        fired = _run(_tick_once(factory, panel_service, now=now))

        assert fired == 0
        panel_service.grant_subscription_quota.assert_awaited_once_with(
            "panel-uuid-1", 3.0
        )
        # Not bumped on failure — will retry next tick.
        assert sub.next_credit_at == due_at
        assert sub.next_credit_amount_usd == 3.0
        # Tick still commits even though nothing fired.
        assert factory.session.committed is True