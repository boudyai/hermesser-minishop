from aiogram import Router

from . import promo_user, referral, start, tenant, tenant_status, trial_handler
from .subscription import router as subscription_router

user_router_aggregate = Router(name="user_router_aggregate")

user_router_aggregate.include_router(promo_user.router)
user_router_aggregate.include_router(trial_handler.router)
user_router_aggregate.include_router(start.router)
user_router_aggregate.include_router(tenant_status.router)
user_router_aggregate.include_router(tenant.router)
user_router_aggregate.include_router(subscription_router)
user_router_aggregate.include_router(referral.router)
