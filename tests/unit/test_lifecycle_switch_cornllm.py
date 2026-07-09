from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.services.hermes_provisioning_service import HermesProvisioningService
from bot.services.panel_api_service import PanelApiService
from bot.services.subscription_service_impl.core import SubscriptionService
from config.settings import Settings

PANEL_UUID = "tenant-uuid"
GIB = 1024**3


def _tariffs_payload() -> dict:
    return {
        "default_tariff": "basic",
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
                "monthly_gb": 50,
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


def _db_user() -> SimpleNamespace:
    return SimpleNamespace(
        user_id=42,
        panel_user_uuid=PANEL_UUID,
        telegram_id=42,
        username="alice",
        first_name="Alice",
        last_name="User",
        email=None,
    )


def _make_sub(
    *,
    tariff_key: str = "basic",
    next_credit_at: datetime | None = None,
    next_credit_amount_usd: object = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        subscription_id=11,
        user_id=42,
        panel_user_uuid=PANEL_UUID,
        panel_subscription_uuid="panel-sub",
        tariff_key=tariff_key,
        start_date=datetime(2099, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2099, 4, 1, tzinfo=timezone.utc),
        effective_monthly_price_rub=100,
        premium_topup_balance_bytes=0,
        premium_topup_used_bytes=0,
        premium_used_bytes=0,
        topup_balance_bytes=0,
        regular_bonus_bytes=0,
        regular_unlimited_override=False,
        traffic_used_bytes=0,
        extra_hwid_devices=0,
        hwid_device_limit=3,
        next_credit_at=next_credit_at,
        next_credit_amount_usd=next_credit_amount_usd,
    )


def _hermes_service(settings: Settings) -> tuple[SubscriptionService, HermesProvisioningService]:
    panel = HermesProvisioningService(settings)
    panel.update_user_details_on_panel = AsyncMock(
        return_value={"uuid": PANEL_UUID, "ok": True}
    )
    panel.grant_subscription_quota = AsyncMock(return_value={"ok": True})
    panel.topup_tenant_quota = AsyncMock(return_value={"ok": True})
    return SubscriptionService(settings, panel), panel


def _panel_service(settings: Settings) -> tuple[SubscriptionService, PanelApiService]:
    panel = PanelApiService(settings)
    panel.update_user_details_on_panel = AsyncMock(
        return_value={"uuid": PANEL_UUID, "ok": True}
    )
    return SubscriptionService(settings, panel), panel


def _patches_for_switch(
    user: SimpleNamespace,
    sub: SimpleNamespace,
    updated: SimpleNamespace,
    *,
    admin_assign: bool,
    target_key: str,
    options: dict | None = None,
) -> ExitStack:
    options = options if options is not None else {
        "mode": "period_to_period",
        "remaining_days": 30,
        "recalc_days": 30,
        "paid_diff_rub": 0,
        "target_monthly_rub": 300 if target_key == "plus" else 100,
        "converted_hwid_value_rub": 0,
        "converted_hwid_days": 0,
        "convertible_hwid_purchase_ids": [],
    }
    stack = ExitStack()
    method_name = (
        "calculate_tariff_switch_options"
        if admin_assign
        else "calculate_tariff_switch_options_with_hwid"
    )
    stack.enter_context(patch(
        "bot.services.subscription_service_impl.lifecycle.user_dal.get_user_by_id",
        AsyncMock(return_value=user),
    ))
    stack.enter_context(patch(
        "bot.services.subscription_service_impl.lifecycle.subscription_dal.get_active_subscription_by_user_id",
        AsyncMock(return_value=sub),
    ))
    stack.enter_context(patch(
        "bot.services.subscription_service_impl.lifecycle.tariff_dal.expire_hwid_device_purchases",
        AsyncMock(return_value=0),
    ))
    stack.enter_context(patch(
        "bot.services.subscription_service_impl.lifecycle.tariff_dal.sum_active_hwid_devices",
        AsyncMock(return_value=0),
    ))
    stack.enter_context(patch(
        "bot.services.subscription_service_impl.lifecycle.subscription_dal.update_subscription",
        AsyncMock(return_value=updated),
    ))
    stack.enter_context(patch(
        "bot.services.subscription_service_impl.lifecycle.subscription_dal.deactivate_other_active_subscriptions",
        AsyncMock(),
    ))
    stack.enter_context(patch(
        "bot.services.subscription_service_impl.lifecycle.tariff_dal.create_tariff_change",
        AsyncMock(),
    ))
    stack.enter_context(patch.object(
        SubscriptionService,
        method_name,
        AsyncMock(return_value=options),
    ))
    return stack


def _updated_of(sub: SimpleNamespace, *, target_key: str) -> SimpleNamespace:
    updated = SimpleNamespace(**sub.__dict__)
    updated.tariff_key = target_key
    updated.traffic_limit_bytes = 100 * GIB
    updated.premium_is_limited = False
    updated.effective_monthly_price_rub = 300 if target_key == "plus" else 100
    return updated


class LifecycleSwitchCornllmTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrade_basic_to_plus_calls_grant_with_new_amount(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service, panel = _hermes_service(_make_settings(tmpdir))
            user = _db_user()
            sub = _make_sub(tariff_key="basic")
            updated = _updated_of(sub, target_key="plus")

            with _patches_for_switch(user, sub, updated, admin_assign=False, target_key="plus"):
                result = await service.switch_tariff_without_payment(
                    AsyncMock(),
                    user_id=42,
                    target_tariff_key="plus",
                    mode="recalc_days",
                )

        panel.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 3.0)
        panel.topup_tenant_quota.assert_not_awaited()
        self.assertEqual(sub.next_credit_amount_usd, 3.0)
        self.assertEqual(result["tariff_key"], "plus")
        self.assertEqual(result["subscription_id"], 11)

    async def test_downgrade_plus_to_basic_calls_grant_with_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service, panel = _hermes_service(_make_settings(tmpdir))
            user = _db_user()
            sub = _make_sub(tariff_key="plus")
            updated = _updated_of(sub, target_key="basic")

            with _patches_for_switch(user, sub, updated, admin_assign=False, target_key="basic"):
                result = await service.switch_tariff_without_payment(
                    AsyncMock(),
                    user_id=42,
                    target_tariff_key="basic",
                    mode="recalc_days",
                )

        panel.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 0.0)
        panel.topup_tenant_quota.assert_not_awaited()
        self.assertEqual(result["tariff_key"], "basic")

    async def test_upgrade_updates_next_credit_amount_usd(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service, panel = _hermes_service(_make_settings(tmpdir))
            user = _db_user()
            existing_next_at = datetime(2099, 7, 30, tzinfo=timezone.utc)
            sub = _make_sub(
                tariff_key="basic",
                next_credit_at=existing_next_at,
                next_credit_amount_usd=0,
            )
            updated = _updated_of(sub, target_key="plus")

            with _patches_for_switch(user, sub, updated, admin_assign=False, target_key="plus"):
                await service.switch_tariff_without_payment(
                    AsyncMock(),
                    user_id=42,
                    target_tariff_key="plus",
                    mode="recalc_days",
                )

        panel.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 3.0)
        self.assertEqual(sub.next_credit_amount_usd, 3.0)
        # next_credit_at is a schedule timing, unaffected by tariff content
        self.assertEqual(sub.next_credit_at, existing_next_at)

    async def test_downgrade_clears_next_credit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service, panel = _hermes_service(_make_settings(tmpdir))
            user = _db_user()
            sub = _make_sub(
                tariff_key="plus",
                next_credit_at=datetime(2099, 7, 30, tzinfo=timezone.utc),
                next_credit_amount_usd=3.0,
            )
            updated = _updated_of(sub, target_key="basic")

            with _patches_for_switch(user, sub, updated, admin_assign=False, target_key="basic"):
                await service.switch_tariff_without_payment(
                    AsyncMock(),
                    user_id=42,
                    target_tariff_key="basic",
                    mode="recalc_days",
                )

        panel.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 0.0)
        self.assertIsNone(sub.next_credit_amount_usd)
        self.assertIsNone(sub.next_credit_at)

    async def test_non_hermes_mode_skips_grant(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = _make_settings(tmpdir, hermes=False)
            service, panel = _panel_service(settings)
            user = _db_user()
            sub = _make_sub(tariff_key="basic")
            updated = _updated_of(sub, target_key="plus")

            with _patches_for_switch(user, sub, updated, admin_assign=False, target_key="plus"):
                result = await service.switch_tariff_without_payment(
                    AsyncMock(),
                    user_id=42,
                    target_tariff_key="plus",
                    mode="recalc_days",
                )

        if hasattr(panel, "grant_subscription_quota"):
            panel.grant_subscription_quota.assert_not_awaited()
        self.assertEqual(result["tariff_key"], "plus")
        self.assertIsNone(sub.next_credit_amount_usd)
        self.assertIsNone(sub.next_credit_at)

    async def test_grant_exception_does_not_break_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service, panel = _hermes_service(_make_settings(tmpdir))
            panel.grant_subscription_quota.side_effect = RuntimeError("core offline")
            user = _db_user()
            sub = _make_sub(tariff_key="basic")
            updated = _updated_of(sub, target_key="plus")

            with self.assertLogs("root", level="ERROR") as log_ctx, _patches_for_switch(
                user, sub, updated, admin_assign=False, target_key="plus"
            ):
                result = await service.switch_tariff_without_payment(
                    AsyncMock(),
                    user_id=42,
                    target_tariff_key="plus",
                    mode="recalc_days",
                )

        panel.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 3.0)
        self.assertEqual(result["tariff_key"], "plus")
        self.assertEqual(result["subscription_id"], 11)
        joined = "\n".join(log_ctx.output)
        self.assertIn("CornLLM tariff-switch grant failed", joined)
        self.assertIn(PANEL_UUID, joined)
