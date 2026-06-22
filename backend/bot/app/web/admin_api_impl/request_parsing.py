"""Backward-compatible imports for admin API request parsing helpers."""

from bot.app.web.request_parsing import parse_body, parse_body_or_400

__all__ = ["parse_body", "parse_body_or_400"]
