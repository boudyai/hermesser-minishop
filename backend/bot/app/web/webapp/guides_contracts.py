from __future__ import annotations

from bot.app.web.route_contracts import (
    RouteContract,
    ok_envelope_for,
)

from .contract_schemas import (
    PublicSubscriptionGuidesOut,
    SubscriptionGuidesOut,
    public_contract,
    user_contract,
)

GUIDES_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "subscription_guides_route": user_contract(
        response_schema=ok_envelope_for(SubscriptionGuidesOut),
        models=(SubscriptionGuidesOut,),
    ),
    "public_subscription_guides_route": public_contract(
        response_schema=ok_envelope_for(PublicSubscriptionGuidesOut),
        models=(PublicSubscriptionGuidesOut,),
    ),
}
