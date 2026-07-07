from __future__ import annotations

from bot.app.web.route_contracts import (
    RouteContract,
    ok_envelope_for,
)

from .contract_schemas import WebappBootstrapOut, WebappI18nOut, public_contract

ASSET_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "bootstrap_route": public_contract(
        response_schema=ok_envelope_for(WebappBootstrapOut),
        models=(WebappBootstrapOut,),
    ),
    "i18n_route": public_contract(
        response_schema=ok_envelope_for(WebappI18nOut),
        models=(WebappI18nOut,),
    ),
}
