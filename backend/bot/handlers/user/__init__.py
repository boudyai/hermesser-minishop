from aiogram import Router

from . import backup, promo_user, referral, start, tenant, trial_handler

# TODO: after splitting subscription into a package, replace this import
from .subscription import router as subscription_router

user_router_aggregate = Router(name="user_router_aggregate")

user_router_aggregate.include_router(promo_user.router)
user_router_aggregate.include_router(trial_handler.router)
user_router_aggregate.include_router(start.router)
user_router_aggregate.include_router(tenant.router)
user_router_aggregate.include_router(subscription_router)
user_router_aggregate.include_router(referral.router)
user_router_aggregate.include_router(backup.router)
