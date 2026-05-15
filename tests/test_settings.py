import json
import unittest

from pydantic import ValidationError

from config.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_blank_postgres_password_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                BOT_TOKEN="token",
                POSTGRES_USER="app_user",
                POSTGRES_PASSWORD="",
            )

    def test_webapp_secrets_are_generated_when_missing(self):
        settings = Settings(
            _env_file=None,
            BOT_TOKEN="token",
            POSTGRES_USER="app_user",
            POSTGRES_PASSWORD="app_password",
        )

        self.assertTrue(settings.WEBAPP_SESSION_SECRET)
        self.assertTrue(settings.WEBHOOK_SECRET_TOKEN)
        self.assertEqual(settings.WEBAPP_SESSION_TTL_SECONDS, 86400)

    def test_deprecated_webapp_appearance_env_values_are_ignored(self):
        settings = Settings(
            _env_file=None,
            BOT_TOKEN="token",
            POSTGRES_USER="app_user",
            POSTGRES_PASSWORD="app_password",
            WEBAPP_PRIMARY_COLOR="#ff0000",
            WEBAPP_LOGO_URL="https://cdn.example.com/logo.png",
            WEBAPP_LOGO_USE_EMOJI=True,
            WEBAPP_LOGO_EMOJI="🔥",
            WEBAPP_LOGO_EMOJI_FONT="twemoji",
            WEBAPP_FAVICON_USE_CUSTOM=True,
            WEBAPP_FAVICON_URL="https://cdn.example.com/favicon.png",
            WEBAPP_LOGO_FAVICON_URL="/webapp-favicon/abcdef1234567890/icon-180.png",
        )

        self.assertEqual(settings.WEBAPP_PRIMARY_COLOR, "#00fe7a")
        self.assertIsNone(settings.WEBAPP_LOGO_URL)
        self.assertFalse(settings.WEBAPP_LOGO_USE_EMOJI)
        self.assertEqual(settings.WEBAPP_LOGO_EMOJI, "🫥")
        self.assertEqual(settings.WEBAPP_LOGO_EMOJI_FONT, "system")
        self.assertFalse(settings.WEBAPP_FAVICON_USE_CUSTOM)
        self.assertIsNone(settings.WEBAPP_FAVICON_URL)
        self.assertIsNone(settings.WEBAPP_LOGO_FAVICON_URL)

    def test_tariffs_config_missing_uses_legacy_fallback(self):
        settings = Settings(
            _env_file=None,
            BOT_TOKEN="token",
            POSTGRES_USER="app_user",
            POSTGRES_PASSWORD="app_password",
            TARIFFS_CONFIG_PATH="missing-tariffs.json",
            TRAFFIC_PACKAGES="10:199",
        )

        self.assertIsNone(settings.tariffs_config)
        self.assertTrue(settings.traffic_sale_mode)

    def test_existing_tariffs_config_disables_legacy_traffic_mode(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tariffs.json"
            path.write_text(
                json.dumps(
                    {
                        "default_tariff": "standard",
                        "tariffs": [
                            {
                                "key": "standard",
                                "names": {"ru": "Стандарт"},
                                "descriptions": {},
                                "squad_uuids": ["uuid"],
                                "billing_model": "period",
                                "monthly_gb": 100,
                                "prices_rub": {"1": 150},
                                "prices_stars": {"1": 0},
                                "enabled_periods": [1],
                                "enabled": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            settings = Settings(
                _env_file=None,
                BOT_TOKEN="token",
                POSTGRES_USER="app_user",
                POSTGRES_PASSWORD="app_password",
                TARIFFS_CONFIG_PATH=str(path),
                TRAFFIC_PACKAGES="10:199",
            )

            self.assertIsNotNone(settings.tariffs_config)
            self.assertFalse(settings.traffic_sale_mode)

    def test_trial_traffic_strategy_is_available(self):
        settings = Settings(
            _env_file=None,
            BOT_TOKEN="token",
            POSTGRES_USER="app_user",
            POSTGRES_PASSWORD="app_password",
            TRIAL_TRAFFIC_STRATEGY="WEEK",
        )

        self.assertEqual(settings.TRIAL_TRAFFIC_STRATEGY, "WEEK")

    def test_tariff_warning_levels_are_parsed(self):
        settings = Settings(
            _env_file=None,
            BOT_TOKEN="token",
            POSTGRES_USER="app_user",
            POSTGRES_PASSWORD="app_password",
            TARIFF_TRAFFIC_WARNING_LEVELS="90,85,bad,95,90,100,0",
        )

        self.assertEqual(settings.tariff_traffic_warning_levels, [85, 90, 95])
