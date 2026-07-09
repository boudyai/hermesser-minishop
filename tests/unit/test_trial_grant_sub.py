from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.services.hermes_provisioning_service import HermesProvisioningService
from bot.services.panel_api_service import PanelApiService
from bot.services.subscription_service_impl.core import SubscriptionService
from config.settings import Settings

PANEL_UUID = "trial-tenant-uuid"
USER_ID = 42


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
                "prices_rub": {"1": 300},
                "enabled_periods": [1],
                "included_cornllm_balance_rub": 0,
                "enabled": True,
            }
        ],
    }


def _make_settings(tmpdir, **overrides):
    config_path = f"{tmpdir}/tariffs.json"
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(_tariffs_payload(), fh)
    values = {
        "_env_file": None,
        "BOT_TOKEN": "token",
        "POSTGRES_USER": "app_user",
        "POSTGRES_PASSWORD": "app_password",
        "TARIFFS_CONFIG_PATH": config_path,
        "PANEL_API_URL": "http://core:9999",
        "PANEL_API_KEY": "test-key",
        "PANEL_WRITE_MODE": "hermes",
        "TRIAL_ENABLED": True,
        "TRIAL_DURATION_DAYS": 3,
        "TRIAL_TRAFFIC_LIMIT_GB": 5,
        "TRIAL_TRAFFIC_STRATEGY": "NO_RESET",
        "TRIAL_CORNLLM_CREDIT_USD": 0.25,
    }
    values.update(overrides)
    return Settings(**values)


def _db_user():
    return SimpleNamespace(
        user_id=USER_ID,
        panel_user_uuid=PANEL_UUID,
        telegram_id=USER_ID,
        username="trialer",
        first_name="Trial",
        last_name="User",
        email=None,
    )


def _dal_patches(stack):
    stack.enter_context(
        patch(
            "bot.services.subscription_service_impl.trial.user_dal.get_user_by_id",
            AsyncMock(return_value=_db_user()),
        )
    )
    stack.enter_context(
        patch(
            "bot.services.subscription_service_impl.trial.subscription_dal.deactivate_other_active_subscriptions",
            AsyncMock(),
        )
    )
    stack.enter_context(
        patch(
            "bot.services.subscription_service_impl.trial.subscription_dal.upsert_subscription",
            AsyncMock(),
        )
    )


class TrialGrantSubscriptionQuotaTests(unittest.IsolatedAsyncioTestCase):
    def _hermes_service(self, settings):
        panel_service = HermesProvisioningService(settings)
        panel_service.update_user_details_on_panel = AsyncMock(
            return_value={"subscriptionUrl": "https://panel/sub", "shortUuid": "short"}
        )
        panel_service.grant_subscription_quota = AsyncMock(return_value={"ok": True})
        panel_service.topup_tenant_quota = AsyncMock(return_value={"ok": True})
        return SubscriptionService(settings, panel_service)

    def _panel_service(self, settings):
        panel_service = PanelApiService(settings)
        panel_service.update_user_details_on_panel = AsyncMock(
            return_value={"subscriptionUrl": "https://panel/sub", "shortUuid": "short"}
        )
        panel_service.grant_subscription_quota = AsyncMock(return_value={"ok": True})
        return panel_service

    async def test_trial_calls_grant_subscription_quota_not_topup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(_make_settings(tmpdir))
            service.has_trial_blocking_subscription = AsyncMock(return_value=False)
            service._get_or_create_panel_user_link_details = AsyncMock(
                return_value=(PANEL_UUID, "panel-sub-uuid", "short", True)
            )
            with ExitStack() as stack:
                _dal_patches(stack)
                emit_model = stack.enter_context(
                    patch(
                        "bot.services.subscription_service_impl.trial.events.emit_model",
                        AsyncMock(),
                    )
                )
                result = await service.activate_trial_subscription(
                    AsyncMock(), user_id=USER_ID
                )

        panel_service = service.panel_service
        panel_service.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 0.25)
        panel_service.topup_tenant_quota.assert_not_awaited()
        self.assertTrue(result["activated"])
        emit_model.assert_awaited_once()

    async def test_trial_with_zero_credit_still_calls_grant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(
                _make_settings(tmpdir, TRIAL_CORNLLM_CREDIT_USD=0)
            )
            service.has_trial_blocking_subscription = AsyncMock(return_value=False)
            service._get_or_create_panel_user_link_details = AsyncMock(
                return_value=(PANEL_UUID, "panel-sub-uuid", "short", True)
            )
            with ExitStack() as stack:
                _dal_patches(stack)
                stack.enter_context(
                    patch(
                        "bot.services.subscription_service_impl.trial.events.emit_model",
                        AsyncMock(),
                    )
                )
                result = await service.activate_trial_subscription(
                    AsyncMock(), user_id=USER_ID
                )

        panel_service = service.panel_service
        panel_service.grant_subscription_quota.assert_awaited_once_with(PANEL_UUID, 0.0)
        panel_service.topup_tenant_quota.assert_not_awaited()
        self.assertTrue(result["activated"])

    async def test_trial_non_hermes_mode_does_not_call_grant_sub(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = _make_settings(tmpdir, PANEL_WRITE_MODE="live")
            panel_service = self._panel_service(settings)
            service = SubscriptionService(settings, panel_service)
            service.has_trial_blocking_subscription = AsyncMock(return_value=False)
            service._get_or_create_panel_user_link_details = AsyncMock(
                return_value=(PANEL_UUID, "panel-sub-uuid", "short", True)
            )
            with ExitStack() as stack:
                _dal_patches(stack)
                stack.enter_context(
                    patch(
                        "bot.services.subscription_service_impl.trial.events.emit_model",
                        AsyncMock(),
                    )
                )
                result = await service.activate_trial_subscription(
                    AsyncMock(), user_id=USER_ID
                )

        panel_service.grant_subscription_quota.assert_not_awaited()
        self.assertTrue(result["activated"])

    async def test_trial_failure_logs_exception_and_continues(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self._hermes_service(_make_settings(tmpdir))
            service.has_trial_blocking_subscription = AsyncMock(return_value=False)
            service._get_or_create_panel_user_link_details = AsyncMock(
                return_value=(PANEL_UUID, "panel-sub-uuid", "short", True)
            )
            service.panel_service.grant_subscription_quota = AsyncMock(
                side_effect=RuntimeError("core down")
            )
            with ExitStack() as stack:
                _dal_patches(stack)
                emit_model = stack.enter_context(
                    patch(
                        "bot.services.subscription_service_impl.trial.events.emit_model",
                        AsyncMock(),
                    )
                )
                result = await service.activate_trial_subscription(
                    AsyncMock(), user_id=USER_ID
                )

        service.panel_service.grant_subscription_quota.assert_awaited_once_with(
            PANEL_UUID, 0.25
        )
        self.assertTrue(result["activated"])
        emit_model.assert_awaited_once()