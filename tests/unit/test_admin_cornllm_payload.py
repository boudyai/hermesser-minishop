from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.app.web.admin_api_impl.users_listing import (
    _bulk_cornllm_balance_for_users,
    _is_hermes_mode,
)
from bot.services.hermes_provisioning_service import HermesProvisioningService


def _user(user_id: int, panel_uuid: str | None) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id, panel_user_uuid=panel_uuid)


def _panel_service(quotas: dict[str, dict | None]) -> HermesProvisioningService:
    """Build a HermesProvisioningService whose get_tenant_quota returns
    values from `quotas` keyed by panel_uuid (None ⇒ returns None)."""

    async def fake_quota(panel_uuid: str):
        return quotas.get(panel_uuid)

    svc = HermesProvisioningService.__new__(HermesProvisioningService)
    svc.get_tenant_quota = AsyncMock(side_effect=fake_quota)  # type: ignore[method-assign]
    return svc


def test_bulk_cornllm_returns_none_state_when_panel_uuid_missing() -> None:
    users = [_user(1, None), _user(2, "uuid-2")]
    svc = _panel_service({"uuid-2": {"max_budget": 16.0, "spent": 1.5}})

    result = asyncio.run(_bulk_cornllm_balance_for_users(svc, users))

    assert result[1] == {"state": "none"}
    assert result[2]["state"] == "ok"
    assert result[2]["max_budget"] == 16.0
    assert result[2]["spent"] == 1.5


def test_bulk_cornllm_returns_unreachable_when_panel_service_raises() -> None:
    users = [_user(1, "uuid-1")]

    async def boom(panel_uuid: str):  # pragma: no cover - mock body
        raise RuntimeError("core down")

    svc = HermesProvisioningService.__new__(HermesProvisioningService)
    svc.get_tenant_quota = AsyncMock(side_effect=boom)  # type: ignore[method-assign]

    result = asyncio.run(_bulk_cornllm_balance_for_users(svc, users))

    assert result[1] == {"state": "unreachable"}


def test_bulk_cornllm_skips_legacy_panel_service() -> None:
    """In Remnawave mode the panel service is the legacy client,
    not HermesProvisioningService; we must not try to call
    get_tenant_quota on it. Empty result, no exception."""
    legacy_svc = SimpleNamespace(get_tenant_quota=lambda *a, **kw: None)
    users = [_user(1, "uuid-1")]

    result = asyncio.run(_bulk_cornllm_balance_for_users(legacy_svc, users))

    assert result == {}


def test_bulk_cornllm_returns_empty_when_no_panel_service() -> None:
    """Legacy mode (or any caller that didn't resolve the panel
    service) gets an empty dict; the per-user payload then falls
    back to state=none."""
    result = asyncio.run(_bulk_cornllm_balance_for_users(None, [_user(1, "uuid-1")]))
    assert result == {}


def test_is_hermes_mode_matches_panel_settings() -> None:
    hermes = SimpleNamespace(panel_settings=SimpleNamespace(write_mode="hermes"))
    legacy = SimpleNamespace(panel_settings=SimpleNamespace(write_mode="remnawave"))
    legacy_none = SimpleNamespace(panel_settings=None)
    broken = SimpleNamespace(panel_settings=SimpleNamespace(write_mode=None))

    assert _is_hermes_mode(hermes) is True  # type: ignore[arg-type]
    assert _is_hermes_mode(legacy) is False  # type: ignore[arg-type]
    assert _is_hermes_mode(legacy_none) is False  # type: ignore[arg-type]
    assert _is_hermes_mode(broken) is False  # type: ignore[arg-type]
