"""Direct tests for ``HermesProvisioningService.pause_tenant`` (Stream G.25).

Manual pause (vacation mode) is a new operation distinct from suspend:
no auto-delete countdown, the user resumes via /activate at any time.
Pins:

- 202 from the core -> True (success)
- 409 (state mismatch, e.g. tenant already suspended) -> False + log.error
- 500 (server error) -> False + log.error
- Network exception -> False + log.exception

Mirrors ``test_hermes_provisioning_service_grant_sub.py`` — a
``_FakeResponse`` mock for ``aiohttp.ClientSession.post`` keeps these
tests offline and deterministic.

The companion ``tenant:start`` callback (``start_callback`` in
``handlers/user/tenant.py``) reuses ``update_user_status_on_panel(..., enable=True)``
which the existing tests already cover; the new functionality lives in
the guard extension at provisioning-core, exercised by the
``test_activate_from_paused_unfreezes_and_starts_vm`` test in
``provisioning-core/tests/test_shop_pause_tenant.py``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

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


def _session_with(responses) -> tuple[MagicMock, list[Dict[str, Any]]]:
    """Build a mock aiohttp.ClientSession that returns queued responses in order.

    Returns the session and a list that captures every ``session.post`` call
    (positional URL + kwargs) so tests can assert routing and payload shape.
    """
    session = MagicMock()
    session.closed = False
    calls: list[Dict[str, Any]] = []

    def post(url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        calls.append({"url": url, "kwargs": kwargs})
        if not responses:
            raise AssertionError(f"unexpected POST to {url}")
        return responses.pop(0)

    session.post.side_effect = post
    return session, calls


def _await(coro: Any) -> Any:
    """Run a coroutine to completion. Local import keeps the test
    independent of anyio's loop-policy semantics.
    """
    import asyncio

    if not hasattr(coro, "__await__"):
        raise TypeError(f"expected coroutine, got {type(coro).__name__}")
    return asyncio.run(coro)


# ============================================
# Success
# ============================================


class TestPauseTenantSuccess:
    def test_returns_true_on_202_and_routes_to_pause_endpoint(self) -> None:
        service = _make_service()
        responses = [
            _FakeResponse(
                202,
                {
                    "tenant_id": "tnt-1",
                    "status": "paused",
                    "job_id": "job-abc",
                },
            )
        ]
        session, calls = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.pause_tenant("tnt-1"))

        assert result is True
        assert len(calls) == 1
        assert calls[0]["url"] == "http://core:9999/shop/tenants/tnt-1/pause"
        # No JSON body — the pause endpoint is parameterless (only path UUID).
        assert calls[0]["kwargs"].get("json") is None


# ============================================
# Error paths (mirrors grant-sub error tests)
# ============================================


class TestPauseTenantErrors:
    def test_409_invalid_state_returns_false_and_logs_error(self) -> None:
        """Server returns 409 shop_pause_invalid_state when the tenant is
        already in a non-active, non-provisioning_vm state (e.g. already
        suspended). The wrapper surfaces as False + log.error.
        """
        service = _make_service()
        responses = [
            _FakeResponse(
                409,
                {
                    "detail": {
                        "error_code": "shop_pause_invalid_state",
                        "params": {"state": "suspended"},
                    }
                },
            )
        ]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        with patch("bot.services.hermes_provisioning_service.log") as mock_log:
            result = _await(service.pause_tenant("tnt-2"))

        assert result is False
        mock_log.error.assert_called_once()
        args, _ = mock_log.error.call_args
        assert args[0] == "Pause tenant failed for %s: %s %s"
        assert args[1] == "tnt-2"
        assert args[2] == 409

    def test_500_returns_false_and_logs_error(self) -> None:
        service = _make_service()
        responses = [_FakeResponse(500, {"detail": "kaboom"})]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        with patch("bot.services.hermes_provisioning_service.log") as mock_log:
            result = _await(service.pause_tenant("tnt-3"))

        assert result is False
        mock_log.error.assert_called_once()
        args, _ = mock_log.error.call_args
        assert args[0] == "Pause tenant failed for %s: %s %s"
        assert args[1] == "tnt-3"
        assert args[2] == 500

    def test_network_exception_returns_false_and_logs_exception(self) -> None:
        """aiohttp raises ClientError on transport failures — the wrapper
        catches the broader Exception (matching the existing
        update_tenant_bot_token style) and logs via log.exception so the
        traceback is preserved. Returns False so the bot handler can show
        the localized failure copy.
        """
        service = _make_service()
        session = MagicMock()
        session.closed = False

        def post(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("connection reset by peer")

        session.post.side_effect = post
        service._core_session = session  # type: ignore[assignment]

        with patch("bot.services.hermes_provisioning_service.log") as mock_log:
            result = _await(service.pause_tenant("tnt-4"))

        assert result is False
        mock_log.exception.assert_called_once()
        args, _ = mock_log.exception.call_args
        assert args[0] == "pause_tenant_exception tenant=%s"
        assert args[1] == "tnt-4"


# ============================================
# Idempotency (200/202 both treated the same)
# ============================================


class TestPauseTenantStatusCodes:
    def test_404_tenant_not_found_returns_false(self) -> None:
        """Tenant row not found. False + log.error (caller decides UX)."""
        service = _make_service()
        responses = [_FakeResponse(404, {"detail": "shop_tenant_not_found"})]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        with patch("bot.services.hermes_provisioning_service.log") as mock_log:
            result = _await(service.pause_tenant("missing-tenant"))

        assert result is False
        mock_log.error.assert_called_once()
