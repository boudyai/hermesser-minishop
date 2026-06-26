"""Compatibility shim for admin runtime refresh helper."""

from __future__ import annotations

from bot.app.web.webapp.cache_helpers import (
    refresh_webapp_runtime_after_settings_change,
)

__all__ = ["refresh_webapp_runtime_after_settings_change"]
