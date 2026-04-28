import json
import unittest


from config.tariffs_config import TariffsConfig, load_tariffs_config


def _valid_config():
    return {
        "default_tariff": "standard",
        "topup_packages_default": {
            "rub": [{"gb": 10, "price": 99}],
            "stars": [{"gb": 10, "price": 2500}],
        },
        "tariffs": [
            {
                "key": "standard",
                "names": {"ru": "Стандарт", "en": "Standard"},
                "descriptions": {"ru": "Base"},
                "squad_uuids": ["uuid-1"],
                "billing_model": "period",
                "monthly_gb": 500,
                "prices_rub": {"1": 150},
                "prices_stars": {"1": 0},
                "enabled_periods": [1],
                "enabled": True,
            },
            {
                "key": "traffic",
                "names": {"ru": "Гигабайты"},
                "descriptions": {},
                "squad_uuids": ["uuid-1"],
                "billing_model": "traffic",
                "traffic_packages": {"rub": [{"gb": 10, "price": 199}], "stars": []},
                "enabled": True,
            },
        ],
    }


class TariffsConfigTests(unittest.TestCase):
    def test_valid_tariffs_config_loads(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tariffs.json"
            path.write_text(json.dumps(_valid_config()), encoding="utf-8")

            config = load_tariffs_config(path)

            self.assertIsNotNone(config)
            self.assertEqual(config.default.key, "standard")
            self.assertEqual(config.require("traffic").rub_per_gb_for_conversion(), 19.9)

    def test_missing_config_returns_none(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(load_tariffs_config(Path(tmpdir) / "missing.json"))

    def test_duplicate_keys_rejected(self):
        data = _valid_config()
        data["tariffs"][1]["key"] = "standard"

        with self.assertRaises(ValueError):
            TariffsConfig.model_validate(data)

    def test_default_must_be_enabled(self):
        data = _valid_config()
        data["default_tariff"] = "missing"

        with self.assertRaises(ValueError):
            TariffsConfig.model_validate(data)

    def test_period_price_required_for_enabled_period(self):
        data = _valid_config()
        data["tariffs"][0]["prices_rub"] = {"1": 0}
        data["tariffs"][0]["prices_stars"] = {"1": 0}

        with self.assertRaises(ValueError):
            TariffsConfig.model_validate(data)

    def test_traffic_without_rub_needs_conversion_rate(self):
        data = _valid_config()
        data["tariffs"][1]["traffic_packages"] = {"rub": [], "stars": [{"gb": 10, "price": 2500}]}

        with self.assertRaises(ValueError):
            TariffsConfig.model_validate(data)
