"""bot_username is threaded through ``HermesProvisioningService`` to the
Mini App's "Открыть бота" CTA. Without it, ``HomeScreen`` disables the
button even when the bot is healthy. Pin the contract at the service
boundary so a future refactor that drops the field from the
``/shop/tenants/{id}`` mapping breaks the test.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock

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
    def __init__(self, status: int, payload: dict[str, Any] | None = None) -> None:
        self.status = status
        self._payload = payload
        self._text_value = "" if payload is None else json.dumps(payload)

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def json(self) -> dict[str, Any]:
        assert self._payload is not None
        return self._payload

    async def text(self) -> str:
        return self._text_value


def _session_with(responses: list[_FakeResponse]) -> MagicMock:
    session = MagicMock()
    session.closed = False

    def get(url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        if not responses:
            raise AssertionError(f"unexpected GET to {url}")
        return responses.pop(0)

    session.get.side_effect = get
    return session


def test_get_user_by_uuid_lookup_propagates_bot_username() -> None:
    service = _make_service()
    responses = [
        _FakeResponse(
            200,
            {
                "tenant_id": "tnt-1",
                "status": "active",
                "bot_username": "cornclawerbot",
            },
        )
    ]
    session = _session_with(responses)
    service._core_session = session  # type: ignore[assignment]

    result = asyncio.run(service.get_user_by_uuid_lookup("tnt-1"))

    assert result["ok"] is True
    assert result["user"]["botUsername"] == "cornclawerbot"
    assert result["user"]["status"] == "active"


def test_get_user_by_uuid_lookup_returns_empty_username_when_missing() -> None:
    service = _make_service()
    responses = [
        _FakeResponse(
            200,
            {
                "tenant_id": "tnt-1",
                "status": "active",
            },
        )
    ]
    session = _session_with(responses)
    service._core_session = session  # type: ignore[assignment]

    result = asyncio.run(service.get_user_by_uuid_lookup("tnt-1"))

    assert result["ok"] is True
    assert result["user"]["botUsername"] == ""


def test_get_user_by_uuid_includes_bot_username() -> None:
    service = _make_service()
    responses = [
        _FakeResponse(
            200,
            {
                "tenant_id": "tnt-1",
                "status": "active",
                "bot_username": "cornclawerbot",
            },
        )
    ]
    session = _session_with(responses)
    service._core_session = session  # type: ignore[assignment]

    result = asyncio.run(service.get_user_by_uuid("tnt-1"))

    assert result is not None
    assert result.get("botUsername") == "cornclawerbot"
