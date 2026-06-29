from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.infra.promo_policies import PromoRedemptionContext, evaluate_promo_redemption
from bot.services.promo_effects import PromoEffects, summarize_effects
from db.dal import promo_code_dal

logger = logging.getLogger(__name__)


async def load_payment_promo_effects(
    session: AsyncSession,
    promo_code_id: int | None,
) -> tuple[Any | None, PromoEffects | None]:
    if not promo_code_id:
        return None, None
    promo_model = await promo_code_dal.get_promo_code_by_id(session, promo_code_id)
    if promo_model is None:
        logger.warning("Attached code ID %s was not found.", promo_code_id)
        return None, None
    return promo_model, PromoEffects.from_model(promo_model)


async def consume_payment_promo(
    *,
    session: AsyncSession,
    user_id: int,
    promo_model: Any,
    effects: PromoEffects,
    payment_id: int,
    sale_mode_base: str,
    months: int | None,
    traffic_gb: float | None,
) -> bool:
    promo_code_id = int(getattr(promo_model, "promo_code_id"))
    existing = await promo_code_dal.get_user_activation_for_promo(
        session,
        promo_code_id,
        user_id,
    )
    if existing is not None:
        return int(getattr(existing, "payment_id", 0) or 0) == int(payment_id)

    decision = await evaluate_promo_redemption(
        PromoRedemptionContext(
            session=session,
            user_id=user_id,
            promo_model=promo_model,
            effects=effects,
            sale_mode_base=sale_mode_base,
            months=months,
            traffic_gb=traffic_gb,
            payment_id=payment_id,
        )
    )
    if not decision.allowed:
        logger.warning(
            "Attached code %s was denied at success for user %s: %s",
            promo_code_id,
            user_id,
            decision.reason_key,
        )
        return False

    incremented = await promo_code_dal.increment_promo_code_usage(session, promo_code_id)
    if not incremented:
        return False
    activation = await promo_code_dal.record_promo_activation(
        session,
        promo_code_id,
        user_id,
        payment_id=payment_id,
        effect_summary=summarize_effects(effects),
        bonus_days=effects.bonus_days,
        discount_percent=effects.discount_percent,
        duration_multiplier=effects.duration_multiplier
        if effects.duration_multiplier != 1.0
        else None,
        traffic_multiplier=effects.traffic_multiplier
        if effects.traffic_multiplier != 1.0
        else None,
        applies_to=effects.applies_to,
    )
    return activation is not None
