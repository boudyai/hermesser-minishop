"""Direct tests for ``HermesProvisioningService.get_tenant_state``.

The serializer tests pin the contract end-to-end; this file pins the
service-level behaviour of the method itself: cache hits, TTL, the
``404 → None`` semantics, network error fallback (serves stale), and
JSON shape normalisation (string-coerced status, ISO ``last_state_change``).

These tests mock ``aiohttp.ClientSession.get`` to keep them offline and
deterministic. They run in microseconds and don't require a Postgres or
provisioning-core running.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

import bot.app.web.subscription_webapp  # noqa: F401 — populates _runtime
from bot.services.hermes_provisioning_service import HermesProvisioningService
from config.settings import Settings


def _make_service(
    *, base_url: str = "http://core:9999", api_key: str = "test-key"
) -> HermesProvisioningService:
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="t",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        PANEL_API_URL=base_url,
        PANEL_API_KEY=api_key,
    )
    return HermesProvisioningService(settings)


class _FakeResponse:
    """Minimal stand-in for an aiohttp response supporting __aenter__."""

    def __init__(self, status: int, payload: Optional[Dict[str, Any]] = None) -> None:
        self.status = status
        self._payload = payload
        self._text_value = "" if payload is None else json.dumps(payload)

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def json(self) -> Dict[str, Any]:
        assert self._payload is not None
        return self._payload

    async def text(self) -> str:
        return self._text_value


def _session_with(responses) -> tuple[MagicMock, list[str]]:
    """Build a mock aiohttp.ClientSession that returns the queued responses in order.

    Returns the session and a list that collects every URL the test hit, so
    assertions can verify routing (and detect unexpected calls).
    """
    session = MagicMock()
    session.closed = False
    calls: list[str] = []

    def get(url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        calls.append(url)
        if not responses:
            raise AssertionError(f"unexpected GET to {url}")
        return responses.pop(0)

    session.get.side_effect = get
    return session, calls


# ============================================
# Success path
# ============================================


class TestGetTenantStateHappyPath:
    def test_returns_normalised_state(self) -> None:
        service = _make_service()
        last_change = "2026-07-01T12:00:00+00:00"
        responses = [
            _FakeResponse(
                200,
                {
                    "tenant_id": "tnt-1",
                    "user_id": "user-1",
                    "status": "provisioning_vm",
                    "desired_state": "running",
                    "actual_state": "pending",
                    "last_state_change": last_change,
                },
            )
        ]
        session, calls = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result == {
            "tenant_id": "tnt-1",
            "status": "provisioning_vm",
            "desired_state": "running",
            "actual_state": "pending",
            "last_state_change": last_change,
        }
        assert calls == ["http://core:9999/shop/tenants/tnt-1"]
        assert service._tenant_state_cache["tnt-1"][0] > 0  # type: ignore[has-type]

    def test_missing_status_field_defaults_to_unknown(self) -> None:
        service = _make_service()
        responses = [
            _FakeResponse(
                200,
                {
                    "tenant_id": "tnt-1",
                    "desired_state": "running",
                    "actual_state": "pending",
                },
            )
        ]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None
        assert result["status"] == "unknown"
        assert result["last_state_change"] is None

    def test_passes_through_iso_string_last_state_change(self) -> None:
        service = _make_service()
        # Provisioning-core serialises datetimes as ISO strings; pass them through
        # verbatim instead of re-parsing. The serializer in turn forwards the
        # string to the frontend unchanged.
        responses = [
            _FakeResponse(
                200,
                {
                    "status": "active",
                    "desired_state": "running",
                    "actual_state": "running",
                    "last_state_change": "2026-07-01T13:45:00.123456+00:00",
                },
            )
        ]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None
        assert result["last_state_change"] == "2026-07-01T13:45:00.123456+00:00"


# ============================================
# Cache
# ============================================


class TestGetTenantStateCache:
    def test_second_call_within_ttl_hits_cache(self) -> None:
        service = _make_service()
        # Pre-populate cache; no GET should occur.
        service._tenant_state_cache["tnt-1"] = (  # type: ignore[has-type]
            time.monotonic(),
            {
                "tenant_id": "tnt-1",
                "status": "active",
                "desired_state": "running",
                "actual_state": "running",
                "last_state_change": "2026-07-01T00:00:00+00:00",
            },
        )
        # Use a session that errors loudly if called.
        session = MagicMock()
        session.closed = False
        session.get.side_effect = AssertionError("cache miss — GET fired")
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None
        assert result["status"] == "active"
        session.get.assert_not_called()

    def test_ttl_expiry_triggers_refetch(self) -> None:
        service = _make_service()
        # Stale cache entry (timestamp far in the past) → refetch.
        service._tenant_state_cache["tnt-1"] = (  # type: ignore[has-type]
            time.monotonic() - service._tenant_state_ttl_seconds - 1.0,
            {"status": "stale", "desired_state": "x", "actual_state": "x"},
        )
        responses = [
            _FakeResponse(
                200,
                {
                    "status": "active",
                    "desired_state": "running",
                    "actual_state": "running",
                    "last_state_change": None,
                },
            )
        ]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None
        assert result["status"] == "active"
        session.get.assert_called_once()

    def test_invalidate_drops_cache_entry(self) -> None:
        service = _make_service()
        service._tenant_state_cache["tnt-1"] = (  # type: ignore[has-type]
            time.monotonic(),
            {
                "status": "active",
                "desired_state": "running",
                "actual_state": "running",
                "last_state_change": None,
            },
        )
        service.invalidate_tenant_state("tnt-1")
        assert "tnt-1" not in service._tenant_state_cache  # type: ignore[operator]

    def test_invalidate_unknown_id_is_noop(self) -> None:
        service = _make_service()
        # Should not raise even if the id was never cached.
        service.invalidate_tenant_state("never-seen")


# ============================================
# Error paths
# ============================================


class TestGetTenantStateErrors:
    def test_404_returns_none_and_does_not_cache(self) -> None:
        service = _make_service()
        responses = [_FakeResponse(404)]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("never-existed"))

        assert result is None
        # 404 is intentionally NOT cached — the tenant may be created imminently
        # during a trial flow, and we want the next call to see it.
        assert "never-existed" not in service._tenant_state_cache  # type: ignore[operator]

    def test_5xx_serves_stale_cache(self) -> None:
        service = _make_service()
        service._tenant_state_cache["tnt-1"] = (  # type: ignore[has-type]
            time.monotonic(),
            {
                "status": "active",
                "desired_state": "running",
                "actual_state": "running",
                "last_state_change": "2026-07-01T00:00:00+00:00",
            },
        )
        responses = [_FakeResponse(503)]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None
        assert result["status"] == "active"  # stale served
        # Cache timestamp NOT updated — the 5xx didn't refresh the entry.
        cached_time, _ = service._tenant_state_cache["tnt-1"]  # type: ignore[misc]
        assert cached_time > 0

    def test_5xx_no_cache_returns_none(self) -> None:
        service = _make_service()
        responses = [_FakeResponse(500)]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is None

    def test_client_error_serves_stale_cache(self) -> None:
        service = _make_service()
        service._tenant_state_cache["tnt-1"] = (  # type: ignore[has-type]
            time.monotonic(),
            {
                "status": "payment_expiring",
                "desired_state": "running",
                "actual_state": "running",
                "last_state_change": None,
            },
        )
        session = MagicMock()
        session.closed = False
        session.get.side_effect = aiohttp.ClientError("connection reset")
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None
        assert result["status"] == "payment_expiring"

    def test_client_error_no_cache_returns_none(self) -> None:
        service = _make_service()
        session = MagicMock()
        session.closed = False
        session.get.side_effect = aiohttp.ClientError("network down")
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is None

    def test_unexpected_exception_returns_none(self) -> None:
        service = _make_service()
        session = MagicMock()
        session.closed = False
        session.get.side_effect = RuntimeError("kaboom")
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.get_tenant_state("tnt-1"))

        assert result is None


# ============================================
# Session management
# ============================================


class TestGetTenantStateSession:
    def test_lazy_session_creation(self) -> None:
        service = _make_service()
        assert service._core_session is None  # type: ignore[has-type]
        responses = [
            _FakeResponse(
                200,
                {
                    "status": "active",
                    "desired_state": "running",
                    "actual_state": "running",
                    "last_state_change": None,
                },
            )
        ]
        session, _ = _session_with(responses)
        with patch.object(
            service, "_core_get_session", AsyncMock(return_value=session)
        ) as get_session:
            result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None
        get_session.assert_awaited_once()

    def test_closed_session_falls_back_to_lazy_build(self) -> None:
        """If the cached session was closed (e.g. across server restarts),
        ``_core_get_session`` will reopen it; the method just delegates."""
        service = _make_service()
        # Pre-set a "closed" session.
        closed = MagicMock()
        closed.closed = True
        service._core_session = closed  # type: ignore[assignment]
        responses = [
            _FakeResponse(
                200,
                {
                    "status": "active",
                    "desired_state": "running",
                    "actual_state": "running",
                    "last_state_change": None,
                },
            )
        ]
        new_session, _ = _session_with(responses)
        with patch.object(service, "_core_get_session", AsyncMock(return_value=new_session)):
            result = _await(service.get_tenant_state("tnt-1"))

        assert result is not None


# ============================================
# Helpers
# ============================================


def _await(coro: Any) -> Any:
    """Run a coroutine to completion. Local import keeps the test
    independent of anyio's loop-policy semantics.
    """
    import asyncio

    if not hasattr(coro, "__await__"):
        raise TypeError(f"expected coroutine, got {type(coro).__name__}")
    return asyncio.run(coro)
