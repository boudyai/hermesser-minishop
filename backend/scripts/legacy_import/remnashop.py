"""The Remnashop importer: section orchestration lives here."""

from __future__ import annotations

import logging
from typing import Any

from .remnashop_env import (
    remnashop_post_migration_actions,
)
from .remnashop_settings import _RemnashopSettingsSection

logger = logging.getLogger(__name__)


class RemnashopImporter(_RemnashopSettingsSection):
    async def run(self) -> dict[str, Any]:
        self.tables = await self._source_tables()
        await self._warn_missing_tables()
        if (
            self._should_run("subscriptions")
            or self._should_run("payments")
            or self._should_run("settings")
        ):
            await self.prepare_tariffs()

        if self._should_run("users"):
            await self.import_users()
        if self._should_run("referrals"):
            await self.import_referrals()
        if self._should_run("subscriptions"):
            await self.import_subscriptions()
        if self._should_run("payments"):
            await self.import_payments()
        if self._should_run("promocodes"):
            await self.import_promocodes()
        if self._should_run("settings"):
            await self.import_settings()

        self.summary["post_migration_actions"] = remnashop_post_migration_actions(
            target_webhook_base_url=self.target_webhook_base_url,
            imported_provider_ids=self.imported_payment_provider_ids,
            source_env=self.source_env,
        )

        if self.write_admin_compat_overrides:
            await self._write_admin_overrides()

        return self._plain_summary()
