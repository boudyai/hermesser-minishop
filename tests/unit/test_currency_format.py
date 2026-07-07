"""Tests for bot.utils.currency_format.

The Mini App card, Telegram /status, and my-subscription bot card all
render the same CornLLM budget numbers. These tests pin the kopecks
behavior so a future "round to whole ruble" tweak doesn't regress
the "9.49 ₽ / 0 ₽ / 1500 ₽" math the user has been seeing.
"""

from __future__ import annotations

from bot.utils.currency_format import (
    derive_remaining_usd,
    format_rub,
    format_rub_pair,
    usd_to_rub,
)


def test_usd_to_rub_uses_100_multiplier() -> None:
    assert usd_to_rub(0) == 0.0
    assert usd_to_rub(1) == 100.0
    assert usd_to_rub(15) == 1500.0
    assert usd_to_rub(0.0949) == 9.49


def test_usd_to_rub_handles_none_and_bad_input() -> None:
    assert usd_to_rub(None) is None
    assert usd_to_rub("not-a-number") is None  # type: ignore[arg-type]


def test_format_rub_renders_whole_rubles_without_decimals() -> None:
    assert format_rub(15) == "1500 ₽"
    assert format_rub(0) == "0 ₽"
    assert format_rub(1.0) == "100 ₽"


def test_format_rub_keeps_kopecks_when_fractional() -> None:
    assert format_rub(0.0949) == "9.49 ₽"
    assert format_rub(15.005) == "1500.50 ₽"


def test_format_rub_returns_default_for_missing() -> None:
    assert format_rub(None) == "—"
    assert format_rub(None, default="??") == "??"


def test_format_rub_pair_uses_kopecks_when_needed() -> None:
    assert format_rub_pair(0.0949, 15) == "9.49 ₽ / 1500 ₽"
    assert format_rub_pair(None, 15) == "— / 1500 ₽"
    assert format_rub_pair(0.0949, None) == "9.49 ₽ / —"


def test_derive_remaining_prefers_max_minus_spent_over_cache() -> None:
    # ponytail: cached remaining stays at 8 after a topup but the
    # server has bumped max_budget to 15; deriving 15 - 2 = 13 wins.
    assert derive_remaining_usd(15, 2, cached_remaining_usd=8) == 13.0


def test_derive_remaining_clamps_at_zero() -> None:
    assert derive_remaining_usd(5, 12, cached_remaining_usd=8) == 0.0


def test_derive_remaining_falls_back_to_cache_when_spent_unknown() -> None:
    assert derive_remaining_usd(10, None, cached_remaining_usd=7) == 7.0
    assert derive_remaining_usd(None, None, cached_remaining_usd=7) == 7.0


def test_derive_remaining_returns_none_when_nothing_known() -> None:
    assert derive_remaining_usd(None, None) is None
    assert derive_remaining_usd(None, None, cached_remaining_usd=None) is None
