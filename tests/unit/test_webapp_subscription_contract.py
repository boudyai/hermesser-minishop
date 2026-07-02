"""Contract integrity tests for the ``WEBAPP_SUBSCRIPTION_SCHEMA`` ↔
``_serialize_subscription`` output agreement.

The serializer and the OpenAPI schema must stay in lockstep. If anyone
adds a field to one without the other, the front-end loses the
guarantee that ``openapi.generated.ts`` (drift-guarded in CI) actually
describes what the back-end emits. This file pins the agreement for the
Stream S8 part 2 surface (``tenant_status`` and its three siblings) and
the surrounding subscription shape.

The checks are deliberately hand-rolled instead of pulling in
``jsonschema``: the production schemas are minimal (no ``oneOf``/``$ref``,
flat ``type`` dicts) and the difference between "schema says integer" and
"Python returns int" is small enough to spell out without a library.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import bot.app.web.subscription_webapp  # noqa: F401 — populates _runtime
from bot.app.web.webapp.contract_schemas import WEBAPP_SUBSCRIPTION_SCHEMA
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


def _make_settings(tmpdir: str) -> Settings:
    config_path = Path(tmpdir) / "tariffs.json"
    config_path.write_text(__import__("json").dumps(_tariffs_payload()), encoding="utf-8")
    return Settings(
        _env_file=None,
        BOT_TOKEN="token",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        TARIFFS_CONFIG_PATH=str(config_path),
    )


def _active(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "tariff_key": "standard",
        "status_from_panel": "ACTIVE",
        "end_date": datetime.now(timezone.utc) + timedelta(days=30),
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


def _schema_props() -> set[str]:
    return set(WEBAPP_SUBSCRIPTION_SCHEMA["properties"].keys())


def _schema_required() -> set[str]:
    return set(WEBAPP_SUBSCRIPTION_SCHEMA.get("required", []))


def _additional_props_allowed() -> bool:
    return WEBAPP_SUBSCRIPTION_SCHEMA.get("additionalProperties", True) is not False


class SubscriptionContractIntegrityTests(unittest.TestCase):
    """The serializer output and the OpenAPI schema must stay in lockstep.

    The schema declares ``additionalProperties: False`` — a contract
    drift would either reject a real field (frontend break) or accept an
    undocumented one (silent schema rot). These tests catch both.
    """

    def test_schema_disallows_additional_properties(self) -> None:
        # Ponytail: this is the invariant that protects the contract. If
        # someone flips it to True, the rest of these tests would still
        # pass for the wrong reason.
        self.assertFalse(_additional_props_allowed())

    def test_active_branch_keys_are_a_subset_of_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, _active(), None, "en")
        self.assertTrue(
            set(payload.keys()).issubset(_schema_props()),
            f"serializer returned keys not in schema: {set(payload.keys()) - _schema_props()}",
        )

    def test_inactive_branch_keys_are_a_subset_of_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, None, None, "en")
        self.assertTrue(
            set(payload.keys()).issubset(_schema_props()),
            f"inactive branch returned keys not in schema: {set(payload.keys()) - _schema_props()}",
        )

    def test_required_keys_present_in_active_branch(self) -> None:
        required = _schema_required()
        if not required:
            self.skipTest("schema declares no required keys")
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, _active(), None, "en")
        missing = required - set(payload.keys())
        self.assertFalse(missing, f"missing required keys: {missing}")

    def test_required_keys_present_in_inactive_branch(self) -> None:
        required = _schema_required()
        if not required:
            self.skipTest("schema declares no required keys")
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, None, None, "en")
        missing = required - set(payload.keys())
        self.assertFalse(missing, f"missing required keys: {missing}")


class TenantFieldsContractIntegrityTests(unittest.TestCase):
    """Stream S8 part 2 contract: the four ``tenant_*`` fields are
    declared in the schema AND emitted by the serializer in both
    branches. Catches "schema forgot a field" and "serializer forgot a
    field" mistakes.
    """

    EXPECTED = (
        "tenant_status",
        "tenant_desired_state",
        "tenant_actual_state",
        "tenant_last_state_change",
    )

    def test_all_tenant_fields_declared_in_schema(self) -> None:
        props = _schema_props()
        for field in self.EXPECTED:
            self.assertIn(field, props, f"schema missing {field}")

    def test_all_tenant_fields_have_nullable_string_type(self) -> None:
        for field in self.EXPECTED:
            schema = WEBAPP_SUBSCRIPTION_SCHEMA["properties"][field]
            self.assertEqual(
                schema.get("type"),
                ["string", "null"],
                f"{field} must be nullable string, got {schema}",
            )

    def test_active_branch_emits_all_tenant_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, _active(), None, "en")
        for field in self.EXPECTED:
            self.assertIn(field, payload, f"active branch missing {field}")

    def test_inactive_branch_emits_all_tenant_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(settings, None, None, "en")
        for field in self.EXPECTED:
            self.assertIn(field, payload, f"inactive branch missing {field}")

    def test_tenant_state_propagation_matches_schema_types(self) -> None:
        """If the schema says ``string | null``, the serializer must
        return a string or ``None`` — never a raw int / dict / object
        that the front-end would have to coerce."""
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings(tmp)
            payload = _serialize_subscription(
                settings,
                _active(),
                None,
                "en",
                tenant_state={
                    "status": "provisioning_vm",
                    "desired_state": "running",
                    "actual_state": "pending",
                    "last_state_change": "2026-07-01T12:00:00+00:00",
                },
            )
        for field in self.EXPECTED:
            value = payload[field]
            self.assertIsInstance(
                value,
                (str, type(None)),
                f"{field} should be str|None, got {type(value).__name__}: {value!r}",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
