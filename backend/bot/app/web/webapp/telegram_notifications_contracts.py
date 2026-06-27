from __future__ import annotations

from bot.app.web.route_contracts import (
    BOOLEAN_SCHEMA,
    NULLABLE_STRING_SCHEMA,
    STRING_SCHEMA,
    RouteContract,
    ok_envelope_with,
)

from .contract_schemas import user_contract

TELEGRAM_NOTIFICATIONS_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "account_telegram_notifications_probe_route": user_contract(
        response_schema=ok_envelope_with(
            {
                "telegram_notifications": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ok", "status", "enabled", "start_link"],
                    "properties": {
                        "ok": BOOLEAN_SCHEMA,
                        "status": STRING_SCHEMA,
                        "enabled": BOOLEAN_SCHEMA,
                        "start_link": NULLABLE_STRING_SCHEMA,
                    },
                }
            }
        ),
    ),
}
