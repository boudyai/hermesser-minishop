from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from bot.payment_providers.shared.link_flow import CreatePaymentRequest
from bot.payment_providers.wata import provider as wata_provider


class _FakeWataService:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def create_payment_link(self, **kwargs):
        self.calls.append(kwargs)
        return True, {"id": "link-1", "url": "https://wata.pro/p/link-1"}

    async def try_reuse_pending_link(self, payment):
        return "https://wata.pro/p/reused"

    def profile_enabled(self, provider):
        return provider == "wata_crypto"

    def profile_for_method(self, provider):
        return SimpleNamespace(link_ttl_minutes=23)


def test_crypto_descriptor_creates_link_with_crypto_provider():
    service = _FakeWataService()
    request = CreatePaymentRequest(
        payment=SimpleNamespace(payment_id=42, provider="wata_crypto"),
        user_id=123,
        amount=100.0,
        currency="RUB",
        description="Order #42",
        months=1,
        sale_mode="subscription",
    )

    success, response = asyncio.run(wata_provider._CRYPTO_DESCRIPTOR.create(service, request))

    assert success is True
    assert response["url"] == "https://wata.pro/p/link-1"
    assert service.calls == [
        {
            "payment_db_id": 42,
            "amount": 100.0,
            "currency": "RUB",
            "description": "Order #42",
            "method": "wata_crypto",
        }
    ]


def test_wata_descriptors_keep_profile_specific_guards():
    service = _FakeWataService()
    assert wata_provider._CRYPTO_DESCRIPTOR.webapp_available(service) is True
    assert wata_provider._DESCRIPTOR.webapp_available(service) is False
    assert wata_provider._CRYPTO_DESCRIPTOR.callback_reuse_since_minutes(service, None) == 23

    crypto_payment = SimpleNamespace(provider="wata_crypto")
    fiat_payment = SimpleNamespace(provider="wata")
    assert wata_provider._CRYPTO_DESCRIPTOR.reuse_payment_allowed(crypto_payment, None) is True
    assert wata_provider._CRYPTO_DESCRIPTOR.reuse_payment_allowed(fiat_payment, None) is False
