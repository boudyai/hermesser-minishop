"""User-facing currency / quota formatting helpers.

Single source of truth for how CornLLM (LiteLLM) budget numbers show up
across the Mini App, Telegram bot, and email templates. Everything here
operates on USD-fractional values from the LiteLLM / quota API and emits
the user-facing RUB string with kopecks when the underlying number is
non-integer.

Why kopecks and not whole rubles: LiteLLM bills in fractional USD, and
a tenant who has spent $0.09 (~9.49 ₽) should see "9.49 ₽" — not
"9 ₽" or "10 ₽". Rounding to whole rubles on the way out silently
loses precision and makes the "spent / remaining / max" math look
inconsistent on the status card.
"""

from __future__ import annotations

RUB_PER_USD = 100.0


def usd_to_rub(usd: float | int | None) -> float | None:
    """USD → RUB (kopeck-precision float). Returns None if input is None."""
    if usd is None:
        return None
    try:
        return float(usd) * RUB_PER_USD
    except (TypeError, ValueError):
        return None


def format_rub(
    usd: float | int | None,
    *,
    default: str = "—",
    suffix: str = " ₽",
) -> str:
    """Render a USD value as a ruble string with kopecks when fractional.

    - Whole-ruble amounts render without trailing decimals: `150 ₽`.
    - Sub-ruble amounts keep kopecks: `9.49 ₽`.
    - ``None`` / unparseable values render as ``default``.
    """
    rub = usd_to_rub(usd)
    if rub is None:
        return default
    if abs(rub - round(rub)) < 1e-6:
        return f"{round(rub)}{suffix}"
    return f"{rub:.2f}{suffix}"


def format_rub_pair(
    spent_usd: float | int | None,
    max_usd: float | int | None,
    *,
    default: str = "—",
) -> str:
    """Render "spent / max" ruble copy, e.g. "9.49 / 1500 ₽"."""
    spent_part = format_rub(spent_usd, default=default)
    max_part = format_rub(max_usd, default=default)
    return f"{spent_part} / {max_part}"


def derive_remaining_usd(
    max_budget_usd: float | int | None,
    spent_usd: float | int | None,
    *,
    cached_remaining_usd: float | int | None = None,
) -> float | None:
    """Return the remaining USD value, preferring a live derivation.

    ``max_budget - spent`` is the source of truth whenever both are
    known — topups bump ``max_budget`` but the cached ``remaining``
    column lags until the worker drains ``update_litellm_key`` and the
    next ``fetch_quota`` cycle lands. Without this derivation the UI
    can show ``remaining < old_max_budget`` right after a topup, which
    is the exact "1500 total / 1000 left" mismatch we just shipped a fix
    for.

    Falls back to ``cached_remaining_usd`` if only that is known.
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
