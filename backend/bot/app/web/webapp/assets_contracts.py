from __future__ import annotations

from bot.app.web.route_contracts import (
    STRING_SCHEMA,
    RouteContract,
    loose_object_schema,
    ok_envelope_with,
)

from .contract_schemas import public_contract

ASSET_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "bootstrap_route": public_contract(
        response_schema=ok_envelope_with(
            {
                "config": loose_object_schema(
                    "Runtime Mini App config assembled from settings and theme catalog."
                ),
                "i18n": loose_object_schema(
                    "Locale dictionary keyed by language and translation key."
                ),
            },
        )
    ),
    "i18n_route": public_contract(
        response_schema=ok_envelope_with(
            {
                "scope": STRING_SCHEMA,
                "i18n": loose_object_schema(
                    "Locale dictionary keyed by language and translation key."
                ),
            },
        )
    ),
}
