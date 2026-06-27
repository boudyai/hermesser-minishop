from __future__ import annotations

from bot.app.web.route_contracts import (
    BINARY_RESPONSE_SCHEMA,
    BOOLEAN_SCHEMA,
    NULLABLE_INTEGER_SCHEMA,
    STRING_SCHEMA,
    RouteContract,
    ok_envelope_with,
)

from .contract_schemas import AUTH_RESPONSE_SCHEMA, ME_RESPONSE_SCHEMA, user_contract
from .payloads import (
    WebAppEmailCodePayload,
    WebAppEmailPayload,
    WebAppLanguagePayload,
    WebAppSetPasswordPayload,
    WebAppTelegramAuthPayload,
)

ACCOUNT_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "me_route": user_contract(response_schema=ME_RESPONSE_SCHEMA),
    "account_avatar_route": user_contract(
        response_schema=BINARY_RESPONSE_SCHEMA,
        response_content_type="image/jpeg",
    ),
    "account_language_route": user_contract(
        request_model=WebAppLanguagePayload,
        response_schema=ok_envelope_with({"language": STRING_SCHEMA}),
    ),
    "account_email_request_route": user_contract(
        request_model=WebAppEmailPayload,
        response_schema=ok_envelope_with(
            {
                "already_linked": BOOLEAN_SCHEMA,
                "retry_after": NULLABLE_INTEGER_SCHEMA,
                "email_code": STRING_SCHEMA,
                "code": STRING_SCHEMA,
            },
            required=[],
        ),
    ),
    "account_email_verify_route": user_contract(
        request_model=WebAppEmailCodePayload,
        response_schema=AUTH_RESPONSE_SCHEMA,
    ),
    "account_password_request_route": user_contract(
        response_schema=ok_envelope_with({"retry_after": NULLABLE_INTEGER_SCHEMA}, required=[]),
    ),
    "account_password_confirm_route": user_contract(
        request_model=WebAppSetPasswordPayload,
        response_schema=ok_envelope_with({"password_auth_enabled": BOOLEAN_SCHEMA}),
    ),
    "account_telegram_link_route": user_contract(
        request_model=WebAppTelegramAuthPayload,
        response_schema=AUTH_RESPONSE_SCHEMA,
    ),
}
