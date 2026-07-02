"""Unit tests for the WebAppCornllmTopupPayload validator."""

from __future__ import annotations

import pytest

from bot.app.web.webapp.payloads import WebAppCornllmTopupPayload


def test_cornllm_topup_payload_accepts_minimum() -> None:
    p = WebAppCornllmTopupPayload(amount_rub=100, method="yookassa")
    assert p.amount_rub == 100


def test_cornllm_topup_payload_accepts_large_amount() -> None:
    p = WebAppCornllmTopupPayload(amount_rub=2500.5, method="platega_sbp")
    assert p.amount_rub == 2500.5


@pytest.mark.parametrize("amount", [0, -1, 99.99, 99])
def test_cornllm_topup_payload_rejects_below_minimum(amount: float) -> None:
    with pytest.raises(ValueError):
        WebAppCornllmTopupPayload(amount_rub=amount, method="yookassa")
