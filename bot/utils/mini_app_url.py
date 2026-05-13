"""Helpers for Telegram Mini App URLs (subscription webapp)."""

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config.settings import Settings


def append_query_params(base_url: str, params: dict[str, str]) -> str:
    """Merge params into an existing URL query string (adds or replaces keys)."""
    raw = (base_url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            existing.pop(key, None)
        else:
            existing[key] = str(value)
    query = urlencode(existing)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def subscription_mini_app_topup_url(settings: Settings, kind: str) -> Optional[str]:
    """Return Mini App URL that opens the traffic top-up flow for ``kind`` (``regular`` or ``premium``)."""  # noqa: E501
    base = str(getattr(settings, "SUBSCRIPTION_MINI_APP_URL", None) or "").strip()
    if not base:
        return None
    normalized = "premium" if str(kind or "").strip().lower() == "premium" else "regular"
    return append_query_params(base, {"topup": normalized})
