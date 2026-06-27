from __future__ import annotations

from bot.app.web.route_contracts import INTEGER_SCHEMA, RouteContract, ok_envelope_with, schema_ref
from bot.app.web.support_schemas import SupportCountsOut, SupportMessageOut, SupportTicketOut

from .contract_schemas import user_contract
from .payloads import CreateTicketPayload, TicketReplyPayload

SUPPORT_ROUTE_CONTRACTS: dict[str, RouteContract] = {
    "support_tickets_route": user_contract(
        response_schema=ok_envelope_with(
            {
                "tickets": {
                    "type": "array",
                    "items": schema_ref(SupportTicketOut),
                },
                "counts": schema_ref(SupportCountsOut),
            }
        ),
        models=(SupportCountsOut, SupportTicketOut),
    ),
    "support_create_ticket_route": user_contract(
        request_model=CreateTicketPayload,
        response_schema=ok_envelope_with({"ticket": schema_ref(SupportTicketOut)}),
        models=(CreateTicketPayload, SupportTicketOut),
    ),
    "support_ticket_detail_route": user_contract(
        response_schema=ok_envelope_with(
            {
                "ticket": schema_ref(SupportTicketOut),
                "messages": {
                    "type": "array",
                    "items": schema_ref(SupportMessageOut),
                },
            }
        ),
        models=(SupportMessageOut, SupportTicketOut),
    ),
    "support_ticket_reply_route": user_contract(
        request_model=TicketReplyPayload,
        response_schema=ok_envelope_with(
            {
                "ticket": schema_ref(SupportTicketOut),
                "message": schema_ref(SupportMessageOut),
            }
        ),
        models=(SupportMessageOut, SupportTicketOut, TicketReplyPayload),
    ),
    "support_ticket_read_route": user_contract(response_schema=ok_envelope_with()),
    "support_unread_route": user_contract(
        response_schema=ok_envelope_with({"unread": INTEGER_SCHEMA}),
    ),
}
