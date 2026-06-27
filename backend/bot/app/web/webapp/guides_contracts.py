from __future__ import annotations

from bot.app.web.route_contracts import (
    BOOLEAN_SCHEMA,
    NULLABLE_STRING_SCHEMA,
    RouteContract,
    loose_object_schema,
    ok_envelope_with,
)

from .contract_schemas import public_contract, user_contract

GUIDES_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "subscription_guides_route": user_contract(
        response_schema=ok_envelope_with(
            {
                "enabled": BOOLEAN_SCHEMA,
                "config": loose_object_schema(
                    "Resolved subscription guide config from admin override or panel."
                ),
                "source": NULLABLE_STRING_SCHEMA,
            },
            required=["enabled"],
        )
    ),
    "public_subscription_guides_route": public_contract(
        response_schema=ok_envelope_with(
            {
                "enabled": BOOLEAN_SCHEMA,
                "config": loose_object_schema(
                    "Resolved subscription guide config from admin override or panel."
                ),
                "source": NULLABLE_STRING_SCHEMA,
                "subscription": loose_object_schema(
                    "Public install subscription context resolved by share token."
                ),
            },
            required=["enabled"],
        )
    ),
}
