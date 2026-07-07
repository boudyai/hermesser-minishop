"""Tests for ``HermesProvisioningService.update_tenant_bot_token``.

The new method pushes a freshly-saved bot token to provisioning-core via
``PUT /shop/tenants/{id}/bot_token`` so the worker drains an
``update_secrets`` job immediately. Without this, the running bot keeps
using the old token until the next trial/paid activation.

We mock ``aiohttp.ClientSession.put`` to keep the tests offline and
deterministic. The method should:
- return ``True`` on 202;
- return ``False`` on 4xx/5xx;
- swallow ``aiohttp.ClientError`` and return ``False``;
- send the token in the JSON body.

Ponytail: tests are written as ``def`` (not ``async def``) and dispatch
the coroutine via the local ``_await`` helper, matching the
``test_hermes_tenant_state_service`` pattern (avoids pulling
``pytest-asyncio``).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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


def _await(coro: Any) -> Any:
    if not hasattr(coro, "__await__"):
        raise TypeError(f"expected coroutine, got {type(coro).__name__}")
    return asyncio.run(coro)


class _FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any] | None = None) -> None:
        self.status = status
        self._payload = payload
        self._text_value = "" if payload is None else json.dumps(payload)

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def text(self) -> str:
        return self._text_value


def _patched_session(
    service: HermesProvisioningService, fake: _FakeResponse
) -> list[dict[str, Any]]:
    """Patch ``_core_get_session`` so the next ``.put(...)`` returns ``fake``.

    Returns a list that captures each call's JSON body so tests can
    assert what was sent.
    """
    captured: list[dict[str, Any]] = []

    def put(url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        if "json" in kwargs:
            captured.append(kwargs["json"])
        return fake

    session = MagicMock()
    session.closed = False
    session.put.side_effect = put
    service._core_get_session = AsyncMock(return_value=session)  # type: ignore[method-assign]
    return captured


def test_update_tenant_bot_token_succeeds_on_202() -> None:
    service = _make_service()
    fake = _FakeResponse(202, {"status": "active", "job_id": "j1"})
    bodies = _patched_session(service, fake)

    result = _await(service.update_tenant_bot_token("tenant-uuid", "123:abc"))
    assert result is True
    assert bodies == [{"bot_token": "123:abc"}]


def test_update_tenant_bot_token_returns_false_on_409() -> None:
    service = _make_service()
    fake = _FakeResponse(409)  # text "409: Conflict"
    _patched_session(service, fake)

    result = _await(service.update_tenant_bot_token("tenant-uuid", "123:abc"))
    assert result is False


def test_update_tenant_bot_token_returns_false_on_500() -> None:
    service = _make_service()
    fake = _FakeResponse(500)
    _patched_session(service, fake)

    result = _await(service.update_tenant_bot_token("tenant-uuid", "123:abc"))
    assert result is False


def test_update_tenant_bot_token_swallows_network_error() -> None:
    service = _make_service()
    session = MagicMock()
    session.closed = False

    class _BrokenEnter:
        async def __aenter__(self) -> Any:
            raise aiohttp.ClientError("connection refused")

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    session.put = MagicMock(return_value=_BrokenEnter())
    service._core_get_session = AsyncMock(return_value=session)  # type: ignore[method-assign]

    result = _await(service.update_tenant_bot_token("tenant-uuid", "123:abc"))
    assert result is False
