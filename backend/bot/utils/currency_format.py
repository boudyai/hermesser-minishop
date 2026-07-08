"""User-facing currency / quota formatting helpers.

The shop operates in USD. ``USD_EXCHANGE_RATE`` (RUB per 1 USD) is used
only when Platega SBP needs a ruble amount — set via the ``USD_EXCHANGE_RATE``
env var, defaults to 100.
"""

from __future__ import annotations

import os
from typing import Optional

USD_EXCHANGE_RATE = float(os.getenv("USD_EXCHANGE_RATE", "100.0"))


def usd_to_rub(usd: float | int | None) -> Optional[float]:
    """USD → RUB at the configured rate. Used for Platega SBP payments."""
    if usd is None:
        return None
    try:
        return round(float(usd) * USD_EXCHANGE_RATE, 2)
    except (TypeError, ValueError):
        return None


def rub_to_usd(rub: float | int | None) -> Optional[float]:
    """RUB → USD at the configured rate. Used for converting admin-entered
    ruble amounts (e.g. included_cornllm_balance_rub) to USD credits."""
    if rub is None:
        return None
    try:
        return round(float(rub) / USD_EXCHANGE_RATE, 2)
    except (TypeError, ValueError):
        return None


def format_usd(
    usd: float | int | None,
    *,
    default: str = "—",
) -> str:
    """Render a USD value as a dollar string with cents when fractional.

    - Whole-dollar amounts render without decimals: ``$3``.
    - Fractional amounts keep cents: ``$3.75``.
    - ``None`` / unparseable values render as ``default``.
    """
    if usd is None:
        return default
    try:
        u = float(usd)
    except (TypeError, ValueError):
        return default
    if abs(u - round(u)) < 1e-6:
        return f"${int(round(u))}"
    return f"${u:.2f}"


def format_rub(
    usd: float | int | None,
    *,
    default: str = "—",
    suffix: str = " ₽",
) -> str:
    """Render a USD value as a ruble string. Legacy — new code should use
    ``format_usd``; this exists only for admin-side display of
    ruble-configured fields (e.g. tariff editor shows ``included_cornllm_balance_rub``
    raw value as ₽)."""
    rub = usd_to_rub(usd)
    if rub is None:
        return default
    if abs(rub - round(rub)) < 1e-6:
        return f"{int(round(rub))}{suffix}"
    return f"{rub:.2f}{suffix}"


def format_rub_pair(
    spent_usd: float | int | None,
    max_usd: float | int | None,
    *,
    default: str = "—",
) -> str:
    """Render "spent / max" ruble copy. Legacy — new code should use ``format_usd``."""
    spent_part = format_rub(spent_usd, default=default)
    max_part = format_rub(max_usd, default=default)
    return f"{spent_part} / {max_part}"


def derive_remaining_usd(
    max_budget_usd: float | int | None,
    spent_usd: float | int | None,
    *,
    cached_remaining_usd: float | int | None = None,
) -> Optional[float]:
    """Return the remaining USD value, preferring a live derivation.

    ``max_budget - spent`` is the source of truth whenever both are
    known — topups bump ``max_budget`` but the cached ``remaining``
    column lags until the worker drains ``update_litellm_key`` and the
    next ``fetch_quota`` cycle lands.
    """
    if max_budget_usd is not None and spent_usd is not None:
        try:
            return max(0.0, float(max_budget_usd) - float(spent_usd))
        except (TypeError, ValueError):
            return None
    if cached_remaining_usd is not None:
        try:
            return float(cached_remaining_usd)
        except (TypeError, ValueError):
            return None
    return None
