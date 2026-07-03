from __future__ import annotations

import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from aiohttp import web

from bot.utils.request_security import ip_in_allowlist, request_client_ip


@dataclass(frozen=True)
class WebhookIpCheck:
    client_ip: str | None
    allowed: bool


def check_webhook_source_ip(
    request: web.Request,
    *,
    trusted_ips: Sequence[str] | str | None,
    trusted_proxies: Sequence[str] | str | None,
    allow_empty: bool,
) -> WebhookIpCheck:
    client_ip = request_client_ip(request, trusted_proxies=trusted_proxies)
    if allow_empty and not trusted_ips:
        return WebhookIpCheck(client_ip=client_ip, allowed=True)
    return WebhookIpCheck(
        client_ip=client_ip,
        allowed=ip_in_allowlist(client_ip, trusted_ips),
    )


def constant_time_compare(
    expected: Any,
    received: Any,
    *,
    case_sensitive: bool = True,
) -> bool:
    expected_text = str(expected or "")
    received_text = str(received or "")
    if not case_sensitive:
        expected_text = expected_text.lower()
        received_text = received_text.lower()
    return hmac.compare_digest(expected_text, received_text)
