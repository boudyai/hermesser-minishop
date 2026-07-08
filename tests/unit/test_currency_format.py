"""Tests for bot.utils.currency_format.

The Mini App card, Telegram /status, and my-subscription bot card all
render the same CornLLM budget numbers. These tests pin the helpers
at the default USD_EXCHANGE_RATE=100 and verify the format_usd output.
"""

from __future__ import annotations

from bot.utils.currency_format import (
    derive_remaining_usd,
    format_rub,
    format_rub_pair,
    format_usd,
    rub_to_usd,
    usd_to_rub,
)


def test_rub_to_usd_converts_at_default_rate_100() -> None:
    assert rub_to_usd(0) == 0.0
    assert rub_to_usd(100) == 1.0
    assert rub_to_usd(300) == 3.0
    assert rub_to_usd(150) == 1.5


def test_rub_to_usd_handles_none_and_bad_input() -> None:
    assert rub_to_usd(None) is None
    assert rub_to_usd("not-a-number") is None  # type: ignore[arg-type]


def test_usd_to_rub_uses_default_rate_100() -> None:
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
    assert derive_remaining_usd(15, 2, cached_remaining_usd=8) == 13.0


def test_derive_remaining_clamps_at_zero() -> None:
    assert derive_remaining_usd(5, 12, cached_remaining_usd=8) == 0.0


def test_derive_remaining_falls_back_to_cache_when_spent_unknown() -> None:
    assert derive_remaining_usd(10, None, cached_remaining_usd=7) == 7.0
    assert derive_remaining_usd(None, None, cached_remaining_usd=7) == 7.0


def test_derive_remaining_returns_none_when_nothing_known() -> None:
    assert derive_remaining_usd(None, None) is None
    assert derive_remaining_usd(None, None, cached_remaining_usd=None) is None


def test_format_usd_renders_whole_dollars_without_cents() -> None:
    assert format_usd(3) == "$3"
    assert format_usd(0) == "$0"
    assert format_usd(3.0) == "$3"


def test_format_usd_keeps_cents_when_fractional() -> None:
    assert format_usd(3.75) == "$3.75"
    assert format_usd(0.09) == "$0.09"
    assert format_usd(1.25) == "$1.25"


def test_format_usd_returns_default_for_missing() -> None:
    assert format_usd(None) == "—"
    assert format_usd(None, default="??") == "??"
    assert format_usd("bad") == "—"
