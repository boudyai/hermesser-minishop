from __future__ import annotations

from bot.app.web.route_contracts import (
    BOOLEAN_SCHEMA,
    STRING_SCHEMA,
    RouteContract,
    ok_envelope_with,
)

from .contract_schemas import (
    PAYMENT_RESPONSE_SCHEMA,
    PLAN_OPTIONS_RESPONSE_SCHEMA,
    TARIFF_CHANGE_OPTIONS_RESPONSE_SCHEMA,
    TARIFF_CHANGE_RESPONSE_SCHEMA,
    user_contract,
)
from .payloads import (
    WebAppAutoRenewPayload,
    WebAppPaymentCreatePayload,
    WebAppTariffChangePayload,
)

BILLING_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "subscription_auto_renew_route": user_contract(
        request_model=WebAppAutoRenewPayload,
        response_schema=ok_envelope_with(
            {
                "auto_renew_enabled": BOOLEAN_SCHEMA,
                "provider": STRING_SCHEMA,
                "provider_label": STRING_SCHEMA,
            }
        ),
    ),
    "device_topup_options_route": user_contract(response_schema=PLAN_OPTIONS_RESPONSE_SCHEMA),
    "tariff_topup_options_route": user_contract(response_schema=PLAN_OPTIONS_RESPONSE_SCHEMA),
    "tariff_change_options_route": user_contract(
        response_schema=TARIFF_CHANGE_OPTIONS_RESPONSE_SCHEMA,
    ),
    "tariff_change_route": user_contract(
        request_model=WebAppTariffChangePayload,
        response_schema=TARIFF_CHANGE_RESPONSE_SCHEMA,
    ),
    "tariff_change_payment_route": user_contract(
        request_model=WebAppPaymentCreatePayload,
        response_schema=PAYMENT_RESPONSE_SCHEMA,
    ),
    "create_payment_route": user_contract(
        request_model=WebAppPaymentCreatePayload,
        response_schema=PAYMENT_RESPONSE_SCHEMA,
    ),
    "payment_status_route": user_contract(response_schema=PAYMENT_RESPONSE_SCHEMA),
}
