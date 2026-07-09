"""Direct tests for ``HermesProvisioningService.grant_subscription_quota``.

Stream G: subscription credits use override semantics (not additive).
The server-side endpoint ``POST /shop/tenants/{id}/quota/grant-sub`` was
shipped in provisioning-core commit e35f876. This file pins the wrapper
behaviour: routing, payload shape (amount=0 is sent verbatim, not
filtered out), success/failure return contract, and that 4xx server
validation surfaces as ``None`` (no client-side pre-validation).

Mocking strategy mirrors ``test_hermes_tenant_state_service.py`` — a
``_FakeResponse`` stand-in for ``aiohttp.ClientSession.post`` keeps these
tests offline and deterministic.
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
# Success path
# ============================================


class TestGrantSubscriptionQuotaSuccess:
    def test_returns_parsed_body_and_correct_url(self) -> None:
        service = _make_service()
        response_body = {
            "tenant_id": "tnt-1",
            "new_sub_balance_usd": 3.0,
            "new_topup_balance_usd": 5.0,
            "new_max_budget_usd": 8.0,
            "delta_usd": 1.5,
            "job_id": "job-abc",
        }
        responses = [_FakeResponse(202, response_body)]
        session, calls = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.grant_subscription_quota("tnt-1", 3.0))

        assert result == response_body
        assert len(calls) == 1
        assert calls[0]["url"] == "http://core:9999/shop/tenants/tnt-1/quota/grant-sub"
        assert calls[0]["kwargs"]["json"] == {"amount_usd": 3.0}

    def test_200_status_also_returns_body(self) -> None:
        """Some provisioning-core endpoints return 200 synchronously; pin
        that grant-sub accepts 200 the same way topup does (status in
        (200, 202))."""
        service = _make_service()
        response_body = {
            "tenant_id": "tnt-2",
            "new_sub_balance_usd": 0.0,
            "new_topup_balance_usd": 0.0,
            "new_max_budget_usd": 0.0,
            "delta_usd": 0.0,
        }
        responses = [_FakeResponse(200, response_body)]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.grant_subscription_quota("tnt-2", 0.0))

        assert result == response_body


# ============================================
# amount=0 edge case
# ============================================


class TestGrantSubscriptionQuotaAmountZero:
    def test_amount_zero_is_sent_verbatim_not_filtered_out(self) -> None:
        """amount=0 is a valid override (zeroes sub_balance on plan
        downgrade). The wrapper must NOT pre-filter 0 — pin that 0.0
        arrives at the server as {"amount_usd": 0.0}.
        """
        service = _make_service()
        responses = [
            _FakeResponse(
                202,
                {
                    "tenant_id": "tnt-3",
                    "new_sub_balance_usd": 0.0,
                    "new_topup_balance_usd": 2.0,
                    "new_max_budget_usd": 2.0,
                    "delta_usd": -1.5,
                },
            )
        ]
        session, calls = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        result = _await(service.grant_subscription_quota("tnt-3", 0.0))

        assert result is not None
        assert calls[0]["kwargs"]["json"] == {"amount_usd": 0.0}
        # ``json={"amount_usd": 0.0}`` is a real 0, not a falsy skip.
        assert "amount_usd" in calls[0]["kwargs"]["json"]


# ============================================
# Error paths
# ============================================


class TestGrantSubscriptionQuotaErrors:
    def test_500_returns_none_and_logs_error(self) -> None:
        service = _make_service()
        responses = [_FakeResponse(500, {"detail": "kaboom"})]
        session, _ = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        with patch("bot.services.hermes_provisioning_service.log") as mock_log:
            result = _await(service.grant_subscription_quota("tnt-4", 2.0))

        assert result is None
        mock_log.error.assert_called_once()
        # The log line carries the tenant id and the 500 status; truncate
        # marker confirms body is truncated to 200 chars like topup.
        args, _ = mock_log.error.call_args
        assert args[0] == "Quota grant-sub failed for %s: %s %s"
        assert args[1] == "tnt-4"
        assert args[2] == 500

    def test_400_server_validation_returns_none(self) -> None:
        """Server rejects amount<0 with 400 shop_amount_must_be_non_negative.
        The wrapper must NOT pre-validate — it just relays the 4xx and
        returns None. Pinning this so a future 'be helpful' refactor
        doesn't add client-side validation.
        """
        service = _make_service()
        responses = [
            _FakeResponse(
                400,
                {
                    "detail": {
                        "error_code": "shop_amount_must_be_non_negative",
                        "params": {},
                    }
                },
            )
        ]
        session, calls = _session_with(responses)
        service._core_session = session  # type: ignore[assignment]

        with patch("bot.services.hermes_provisioning_service.log") as mock_log:
            result = _await(service.grant_subscription_quota("tnt-5", -1.0))

        assert result is None
        # Negative was still sent to the server (no client-side guard).
        assert calls[0]["kwargs"]["json"] == {"amount_usd": -1.0}
        mock_log.error.assert_called_once()