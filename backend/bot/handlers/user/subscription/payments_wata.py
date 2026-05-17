import logging
from typing import Optional

from aiogram import F, Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline.user_keyboards import get_payment_url_keyboard
from bot.middlewares.i18n import JsonI18n
from bot.services.wata_service import WataService
from config.settings import Settings
from db.dal import payment_dal

router = Router(name="user_subscription_payments_wata_router")


@router.callback_query(F.data.startswith("pay_wata:"))
async def pay_wata_callback_handler(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    wata_service: WataService,
    session: AsyncSession,
):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key

    if not i18n or not callback.message:
        try:
            await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        except Exception:
            pass
        return

    if not wata_service or not wata_service.configured:
        logging.error("Wata service is not configured or unavailable.")
        try:
            await callback.answer(get_text("payment_service_unavailable_alert"), show_alert=True)
        except Exception:
            pass
        try:
            await callback.message.edit_text(get_text("payment_service_unavailable"))
        except Exception:
            pass
        return

    try:
        _, data_payload = callback.data.split(":", 1)
        parts = data_payload.split(":")
        months = float(parts[0])
        price_rub = float(parts[1])
        sale_mode = parts[2] if len(parts) > 2 else "subscription"
    except (ValueError, IndexError):
        logging.error("Invalid pay_wata data in callback: %s", callback.data)
        try:
            await callback.answer(get_text("error_try_again"), show_alert=True)
        except Exception:
            pass
        return

    user_id = callback.from_user.id
    human_value = str(int(months)) if float(months).is_integer() else f"{months:g}"
    sale_base = sale_mode.split("@", 1)[0].split("|", 1)[0]
    payment_description = (
        get_text("payment_description_traffic", traffic_gb=human_value)
        if sale_base in {"traffic", "traffic_package", "topup", "premium_topup"}
        else (
            get_text("payment_description_hwid_devices", count=int(months))
            if sale_base in {"hwid_device", "hwid_devices"}
            else get_text("payment_description_subscription", months=int(months))
        )
    )
    currency_code = settings.DEFAULT_CURRENCY_SYMBOL or "RUB"

    payment_record_payload = {
        "user_id": user_id,
        "amount": price_rub,
        "currency": currency_code,
        "status": "pending_wata",
        "description": payment_description,
        "subscription_duration_months": int(months) if sale_base == "subscription" else None,
        "provider": "wata",
        "sale_mode": sale_mode,
        "tariff_key": sale_mode.split("@", 1)[1] if "@" in sale_mode else None,
        "purchased_gb": float(months)
        if sale_base in {"traffic", "traffic_package", "topup", "premium_topup"}
        else None,
        "purchased_hwid_devices": int(months)
        if sale_base in {"hwid_device", "hwid_devices"}
        else None,
    }

    try:
        payment_record = await payment_dal.create_payment_record(session, payment_record_payload)
        await session.commit()
    except Exception as e_db_create:
        await session.rollback()
        logging.error(
            "Wata: failed to create payment record for user %s: %s",
            user_id,
            e_db_create,
            exc_info=True,
        )
        try:
            await callback.message.edit_text(get_text("error_creating_payment_record"))
        except Exception:
            pass
        try:
            await callback.answer(get_text("error_try_again"), show_alert=True)
        except Exception:
            pass
        return

    success, response_data = await wata_service.create_payment_link(
        payment_db_id=payment_record.payment_id,
        amount=price_rub,
        currency=currency_code,
        description=payment_description,
    )

    if success:
        payment_link = response_data.get("url")
        provider_identifier = response_data.get("id")

        if provider_identifier:
            try:
                await payment_dal.update_provider_payment_and_status(
                    session,
                    payment_record.payment_id,
                    str(provider_identifier),
                    payment_record.status,
                )
                await session.commit()
            except Exception as e_status:
                await session.rollback()
                logging.error(
                    "Wata: failed to store provider payment id for payment %s: %s",
                    payment_record.payment_id,
                    e_status,
                    exc_info=True,
                )

        if payment_link:
            try:
                await callback.message.edit_text(
                    get_text(
                        key="payment_link_message_traffic"
                        if sale_base in {"traffic", "traffic_package", "topup", "premium_topup"}
                        else "payment_link_message",
                        months=int(months),
                        traffic_gb=human_value,
                    ),
                    reply_markup=get_payment_url_keyboard(
                        payment_link,
                        current_lang,
                        i18n,
                        back_callback=f"subscribe_period:{human_value}",
                        back_text_key="back_to_payment_methods_button",
                    ),
                    disable_web_page_preview=False,
                )
            except Exception as e_edit:
                logging.warning(
                    "Wata: failed to display payment link (%s), sending new message.",
                    e_edit,
                )
                try:
                    await callback.message.answer(
                        get_text(
                            key="payment_link_message_traffic"
                            if sale_base
                            in {"traffic", "traffic_package", "topup", "premium_topup"}
                            else "payment_link_message",
                            months=int(months),
                            traffic_gb=human_value,
                        ),
                        reply_markup=get_payment_url_keyboard(
                            payment_link,
                            current_lang,
                            i18n,
                            back_callback=f"subscribe_period:{human_value}",
                            back_text_key="back_to_payment_methods_button",
                        ),
                        disable_web_page_preview=False,
                    )
                except Exception:
                    pass
            try:
                await callback.answer()
            except Exception:
                pass
            return

        logging.error(
            "Wata: payment link created but missing url for payment %s. Response: %s",
            payment_record.payment_id,
            response_data,
        )

    try:
        await payment_dal.update_payment_status_by_db_id(
            session,
            payment_record.payment_id,
            "failed_creation",
        )
        await session.commit()
    except Exception as e_status:
        await session.rollback()
        logging.error(
            "Wata: failed to mark payment %s as failed_creation: %s",
            payment_record.payment_id,
            e_status,
            exc_info=True,
        )

    try:
        await callback.message.edit_text(get_text("error_payment_gateway"))
    except Exception:
        pass
    try:
        await callback.answer(get_text("error_payment_gateway"), show_alert=True)
    except Exception:
        pass
