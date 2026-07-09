from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.services.hermes_provisioning_service import HermesProvisioningService
from bot.services.panel_api_service import PanelApiService
from bot.services.subscription_service_impl.core import SubscriptionService
from config.settings import Settings

PANEL_UUID = "tenant-uuid"
GIB = 1024**3


def _tariffs_payload():
    return {
        "default_tariff": "plus",
        "tariffs": [
            {
                "key": "plus",
                "names": {"en": "Plus"},
                "descriptions": {"en": "Plus"},
                "squad_uuids": ["main-squad"],
                "premium_squad_uuids": [],
                "billing_model": "period",
                "monthly_gb": 100,
                "prices_rub": {"1": 300, "3": 900},
                "enabled_periods": [1, 3],
                "included_cornllm_balance_rub": 300,
                "enabled": True,
            },
            {
                "key": "basic",
                "names": {"en": "Basic"},
                "descriptions": {"en": "Basic"},
                "squad_uuids": ["main-squad"],
                "premium_squad_uuids": [],
                "billing_model": "period",
                "monthly_gb": 100,
                "prices_rub": {"1": 100, "3": 300},
                "enabled_periods": [1, 3],
                "included_cornllm_balance_rub": 0,
                "enabled": True,
            },
        ],
    }


def _make_settings(tmpdir: str, *, hermes: bool = True) -> Settings:
    config_path = Path(tmpdir) / "tariffs.json"
    config_path.write_text(json.dumps(_tariffs_payload()), encoding="utf-8")
    return Settings(
        _env_file=None,
        BOT_TOKEN="token",
        POSTGRES_USER="app_user",
        POSTGRES_PASSWORD="app_password",
        TARIFFS_CONFIG_PATH=str(config_path),
        PANEL_API_URL="http://core:9999",
        PANEL_API_KEY="test-key",
        PANEL_WRITE_MODE="hermes" if hermes else "live",
    )


def _active_sub(end_date: datetime | None = None):
    return SimpleNamespace(
        subscription_id=41,
        end_date=end_date or datetime(2030, 1, 1, tzinfo=timezone.utc),
        tariff_key="plus",
        topup_balance_bytes=0,
        extra_hwid_devices=0,
        premium_topup_balance_bytes=0,
        premium_topup_used_bytes=0,
        premium_used_bytes=0,
        premium_period_start_at=None,
        regular_bonus_bytes=0,
        regular_unlimited_override=False,
    )


def _db_user():
    return SimpleNamespace(
        user_id=42,
        panel_user_uuid=PANEL_UUID,
        telegram_id=42,
        username="alice",
        first_name="Alice",
        last_name="User",
        email=None,
    )


class LifecycleActivationGrantSubscriptionQuotaTests(unittest.IsolatedAsyncioTestCase):
    def _hermes_service(self, settings: Settings) -> SubscriptionService:
        panel_service = HermesProvisioningService(settings)
        panel_service.update_user_details_on_panel = AsyncMock(
            return_value={"subscriptionUrl": "https://panel/sub", "shortUuid": "short"}
        )
        panel_service.grant_subscription_quota = AsyncMock(return_value={"ok": True})
        panel_service.topup_tenant_quota = AsyncMock(return_value={"ok": True})
        return SubscriptionService(settings, panel_service)

    def _panel_service(self, settings: Settings) -> PanelApiService:
        panel_service = PanelApiService(settings)
        panel_service.update_user_details_on_panel = AsyncMock(
            return_value={"subscriptionUrl": "https://panel/sub", "shortUuid": "short"}
        )
        panel_service.grant_subscription_quota = AsyncMock(return_value={"ok": True})
        return panel_service

    async def _activate(
        self,
        service: SubscriptionService,
        *,
        months: int,
        tariff_key: str,
        current_active_sub=None,
    ):
        updated_sub = SimpleNamespace(
            subscription_id=99,
            next_credit_at="not-reset",
            next_credit_amount_usd="not-reset",
        )
        service._record_payment_context = AsyncMock()
        service._get_or_create_panel_user_link_details = AsyncMock(
            return_value=(PANEL_UUID, "panel-sub-uuid", "old-short", False)
        )
        service._send_payment_success_email = AsyncMock()

        with (
            patch(
                "bot.services.subscription_service_impl.lifecycle_activation.user_dal.get_user_by_id",
                AsyncMock(return_value=_db_user()),
            ),
            patch(
                "bot.services.subscription_service_impl.lifecycle_activation.payment_dal.get_payment_by_db_id",
                AsyncMock(return_value=None),
            ),
            patch(
                "bot.services.subscription_service_impl.lifecycle_activation.subscription_dal.get_active_subscription_by_user_id",
                AsyncMock(return_value=current_active_sub),
            ),
            patch(
                "bot.services.subscription_service_impl.lifecycle_activation.subscription_dal.deactivate_other_active_subscriptions",
                AsyncMock(),
            ),
            patch(
                "bot.services.subscription_service_impl.lifecycle_activation.subscription_dal.upsert_subscription",
                AsyncMock(return_value=updated_sub),
            ),
            patch(
                "bot.services.subscription_service_impl.lifecycle_activation.tariff_dal.get_hwid_device_entitlement_summary",
                AsyncMock(return_value={"active_devices": 0, "active_until": None}),
            ),
        ):
            result = await service.activate_subscription(
                session=AsyncMock(),
                user_id=42,
                months=months,
                payment_amount=300,
                payment_db_id=17,
                provider="manual",
                sale_mode=f"subscription@{tariff_key}",
            )
        return result, updated_sub

    async def test_activate_calls_grant_subscription_quota_not_topup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(_make_settings(tmpdir))

            result, _ = await self._activate(service, months=1, tariff_key="plus")

        panel_service = service.panel_service
        panel_service.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 3.0)
        panel_service.topup_tenant_quota.assert_not_awaited()
        self.assertEqual(result["cornllm_credit_usd"], 3.0)

    async def test_activate_zero_credit_tariff_calls_grant_with_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(_make_settings(tmpdir))

            result, _ = await self._activate(service, months=1, tariff_key="basic")

        panel_service = service.panel_service
        panel_service.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 0.0)
        panel_service.topup_tenant_quota.assert_not_awaited()
        self.assertIsNone(result["cornllm_credit_usd"])

    async def test_activate_single_month_sets_next_credit_at_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(_make_settings(tmpdir))

            _, sub = await self._activate(service, months=1, tariff_key="plus")

        self.assertIsNone(sub.next_credit_at)
        self.assertIsNone(sub.next_credit_amount_usd)

    async def test_activate_multi_month_sets_next_credit_at_thirty_days_out(self) -> None:
        start_date = datetime(2030, 1, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(_make_settings(tmpdir))

            _, sub = await self._activate(
                service,
                months=3,
                tariff_key="plus",
                current_active_sub=_active_sub(start_date),
            )

        self.assertEqual(sub.next_credit_at, start_date + timedelta(days=30))
        self.assertEqual(sub.next_credit_amount_usd, 3.0)

    async def test_activate_multi_month_zero_credit_tariff_sets_next_credit_at_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(_make_settings(tmpdir))

            _, sub = await self._activate(
                service,
                months=3,
                tariff_key="basic",
                current_active_sub=_active_sub(),
            )

        panel_service = service.panel_service
        panel_service.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 0.0)
        self.assertIsNone(sub.next_credit_at)
        self.assertIsNone(sub.next_credit_amount_usd)

    async def test_activate_non_hermes_mode_does_not_call_grant_sub(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = _make_settings(tmpdir, hermes=False)
            panel_service = self._panel_service(settings)
            service = SubscriptionService(settings, panel_service)

            result, _ = await self._activate(service, months=1, tariff_key="plus")

        panel_service.grant_subscription_quota.assert_not_awaited()
        self.assertEqual(result["cornllm_credit_usd"], 3.0)
