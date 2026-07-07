"""Tests for the ``tenant_*`` runtime fields emitted by ``_serialize_subscription``.

In hermes mode the runtime tenant lifecycle (``provisioning_vm``,
``payment_expiring``, ``error``, …) is owned by provisioning-core, not the
shop-side Subscription row. ``_build_user_payload`` fetches it once via
``HermesProvisioningService.get_tenant_state`` and threads it through
``_serialize_subscription`` so HomeScreen can render the in-progress /
grace-period / error states without a second roundtrip.

These tests pin the surface contract:

* when no ``tenant_state`` is passed (sync / test context, non-hermes mode,
  unreachable core) → all four fields are present and null;
* when ``tenant_state`` is passed → all four fields are present and reflect
  the core response (status, desired_state, actual_state, last_state_change);
* the ``!active`` branch keeps the same four null fields, so the response
  shape is stable regardless of subscription state.
"""

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import bot.app.web.subscription_webapp  # noqa: F401 — populates webapp._runtime
from bot.app.web.webapp.serializers import _serialize_subscription
from config.settings import Settings


def _tariffs_payload() -> dict:
    return {
        "default_tariff": "standard",
        "tariffs": [
            {
                "key": "standard",
                "names": {"en": "Standard"},
                "descriptions": {"en": "Base"},
                "squad_uuids": ["main"],
                "billing_model": "period",
                "monthly_gb": 100,
                "prices_rub": {"1": 100},
                "prices_stars": {"1": 0},
                "enabled_periods": [1],
                "hwid_device_limit": 3,
                "enabled": True,
            }
        ],
    }


def _make_settings(tmpdir: str, **overrides: Any) -> Settings:
    config_path = Path(tmpdir) / "tariffs.json"
    config_path.write_text(json.dumps(_tariffs_payload()), encoding="utf-8")
    values: dict[str, Any] = {
        "_env_file": None,
        "BOT_TOKEN": "token",
        "POSTGRES_USER": "u",
        "POSTGRES_PASSWORD": "p",
        "TARIFFS_CONFIG_PATH": str(config_path),
    }
    values.update(overrides)
    return Settings(**values)


def _active(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "tariff_key": "standard",
        "status_from_panel": "ACTIVE",
        "end_date": datetime.now(UTC) + timedelta(days=30),
        "traffic_limit_bytes": 0,
        "traffic_used_bytes": 0,
        "premium_baseline_bytes": 0,
        "premium_topup_balance_bytes": 0,
        "premium_topup_used_bytes": 0,
        "premium_used_bytes": 0,
        "premium_limit_bytes": 0,
        "max_devices": 3,
        "base_hwid_device_limit": 3,
        "extra_hwid_devices": 0,
        "billing_model": "period",
        "tariff_name": "Standard",
        "tariff_description": "Base",
        "premium_title": None,
        "config_link": None,
        "connect_button_url": None,
        "tier_baseline_bytes": 0,
        "topup_balance_bytes": 0,
        "premium_bonus_bytes": 0,
        "regular_bonus_bytes": 0,
        "regular_unlimited_override": False,
        "premium_unlimited_override": False,
        "premium_is_limited": False,
        "premium_squad_labels": [],
        "premium_node_labels": [],
        "period_start_at": None,
        "is_throttled": False,
        "traffic_limit_strategy": "",
    }
    base.update(overrides)
    return base


class TenantRuntimeFieldsTests(unittest.TestCase):
    def test_active_branch_emits_null_tenant_fields_without_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, _active(), None, "en")
        self.assertIn("tenant_status", payload)
        self.assertIn("tenant_desired_state", payload)
        self.assertIn("tenant_actual_state", payload)
        self.assertIn("tenant_last_state_change", payload)
        self.assertIsNone(payload["tenant_status"])
        self.assertIsNone(payload["tenant_desired_state"])
        self.assertIsNone(payload["tenant_actual_state"])
        self.assertIsNone(payload["tenant_last_state_change"])

    def test_inactive_branch_emits_null_tenant_fields_without_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, None, None, "en")
        self.assertIn("tenant_status", payload)
        self.assertIsNone(payload["tenant_status"])
        self.assertIn("tenant_desired_state", payload)
        self.assertIsNone(payload["tenant_desired_state"])
        self.assertIn("tenant_actual_state", payload)
        self.assertIsNone(payload["tenant_actual_state"])
        self.assertIn("tenant_last_state_change", payload)
        self.assertIsNone(payload["tenant_last_state_change"])

    def test_active_branch_propagates_tenant_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(
                settings,
                _active(),
                None,
                "en",
                tenant_state={
                    "tenant_id": "tnt-1",
                    "status": "provisioning_vm",
                    "desired_state": "running",
                    "actual_state": "pending",
                    "last_state_change": "2026-07-01T10:00:00+00:00",
                },
            )
        self.assertEqual(payload["tenant_status"], "provisioning_vm")
        self.assertEqual(payload["tenant_desired_state"], "running")
        self.assertEqual(payload["tenant_actual_state"], "pending")
        self.assertEqual(payload["tenant_last_state_change"], "2026-07-01T10:00:00+00:00")

    def test_inactive_branch_propagates_tenant_state(self):
        """Mid-trial (no active subscription yet) we still want the tenant's
        runtime state on the wire so the UI can show provisioning progress."""
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(
                settings,
                None,
                None,
                "en",
                tenant_state={
                    "tenant_id": "tnt-2",
                    "status": "provisioning_litellm_key",
                    "desired_state": "running",
                    "actual_state": "unknown",
                    "last_state_change": None,
                },
            )
        self.assertEqual(payload["tenant_status"], "provisioning_litellm_key")
        self.assertEqual(payload["tenant_desired_state"], "running")
        self.assertEqual(payload["tenant_actual_state"], "unknown")
        self.assertIsNone(payload["tenant_last_state_change"])

    def test_error_state_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(
                settings,
                _active(),
                None,
                "en",
                tenant_state={
                    "status": "error",
                    "desired_state": "running",
                    "actual_state": "error",
                    "last_state_change": "2026-07-01T11:00:00+00:00",
                },
            )
        self.assertEqual(payload["tenant_status"], "error")
        self.assertEqual(payload["tenant_actual_state"], "error")

    def test_payment_expiring_grace_period_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(
                settings,
                _active(),
                None,
                "en",
                tenant_state={
                    "status": "payment_expiring",
                    "desired_state": "running",
                    "actual_state": "running",
                    "last_state_change": "2026-07-01T09:00:00+00:00",
                },
            )
        self.assertEqual(payload["tenant_status"], "payment_expiring")
        self.assertEqual(payload["tenant_actual_state"], "running")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
