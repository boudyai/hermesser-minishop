"""Compatibility facade for the subscription service."""

from bot.services.subscription_service_impl import _runtime as _runtime
from bot.services.subscription_service_impl.core import SubscriptionService

for _name, _value in vars(_runtime).items():
    if not _name.startswith("__") and _name != "annotations":
        globals()[_name] = _value

SubscriptionService.__module__ = __name__

__all__ = ["SubscriptionService"]
