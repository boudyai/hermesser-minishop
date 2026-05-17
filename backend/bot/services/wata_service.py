import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional, Tuple

from aiogram import Bot
from aiohttp import ClientSession, ClientTimeout, web
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from sqlalchemy.orm import sessionmaker

from bot.keyboards.inline.user_keyboards import get_connect_and_main_keyboard
from bot.middlewares.i18n import JsonI18n
from bot.services.notification_service import NotificationService
from bot.services.referral_service import ReferralService
from bot.services.subscription_service import SubscriptionService
from bot.utils.config_link import prepare_config_links
from bot.utils.request_security import ip_in_allowlist, request_client_ip
from bot.utils.text_sanitizer import sanitize_display_name, username_for_display
from config.settings import Settings
from db.dal import payment_dal, user_dal


class WataService:
    def __init__(
        self,
        *,
        bot: Bot,
        settings: Settings,
        i18n: JsonI18n,
        async_session_factory: sessionmaker,
        subscription_service: SubscriptionService,
        referral_service: ReferralService,
        default_return_url: str,
    ):
        self.bot = bot
        self.settings = settings
        self.i18n = i18n
        self.async_session_factory = async_session_factory
        self.subscription_service = subscription_service
        self.referral_service = referral_service

        self.base_url = (settings.WATA_BASE_URL or "https://api.wata.pro/api/h2h").rstrip("/")
        self.api_token = settings.WATA_API_TOKEN or ""
        self.return_url = settings.WATA_RETURN_URL or f"https://t.me/{default_return_url}"
        self.failed_url = settings.WATA_FAILED_URL or self.return_url
        self.payment_link_ttl_days = settings.WATA_PAYMENT_LINK_TTL_DAYS
        self.verify_webhook_signature = settings.WATA_WEBHOOK_VERIFY_SIGNATURE
        self._public_key_pem = settings.WATA_PUBLIC_KEY

        self._timeout = ClientTimeout(total=20)
        self._session: Optional[ClientSession] = None
        self.configured: bool = bool(settings.WATA_ENABLED and self.api_token)
        if not self.configured:
            logging.warning("WataService initialized but not fully configured. Payments disabled.")

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def _format_amount(amount: float) -> Decimal:
        return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def create_payment_link(
        self,
        *,
        payment_db_id: int,
        amount: float,
        currency: Optional[str],
        description: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        if not self.configured:
            logging.error("WataService is not configured. Cannot create payment link.")
            return False, {"message": "service_not_configured"}

        session = await self._get_session()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.payment_link_ttl_days)
        body: Dict[str, Any] = {
            "amount": float(self._format_amount(amount)),
            "currency": (currency or self.settings.DEFAULT_CURRENCY_SYMBOL or "RUB").upper(),
            "description": description,
            "orderId": str(payment_db_id),
            "successRedirectUrl": self.return_url,
            "failRedirectUrl": self.failed_url,
            "expirationDateTime": expires_at.isoformat().replace("+00:00", "Z"),
        }

        try:
            async with session.post(
                f"{self.base_url}/links",
                json=body,
                headers=self._auth_headers(),
            ) as response:
                response_text = await response.text()
                try:
                    response_data = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    logging.error("Wata create_payment_link: invalid JSON: %s", response_text)
                    return False, {
                        "status": response.status,
                        "message": "invalid_json",
                        "raw": response_text,
                    }
                if response.status != 200:
                    logging.error(
                        "Wata create_payment_link: API error (status=%s, body=%s)",
                        response.status,
                        response_data,
                    )
                    return False, {"status": response.status, "message": response_data}
                return True, response_data
        except Exception as exc:
            logging.exception("Wata create_payment_link: request failed.")
            return False, {"message": str(exc)}

    async def _get_public_key_pem(self) -> Optional[str]:
        if self._public_key_pem:
            return self._public_key_pem.replace("\\n", "\n")

        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/public-key") as response:
                if response.status != 200:
                    logging.error("Wata public key request failed with status %s", response.status)
                    return None
                data = await response.json()
                value = data.get("value") if isinstance(data, dict) else None
                if isinstance(value, str) and value.strip():
                    self._public_key_pem = value
                    return value.replace("\\n", "\n")
        except Exception:
            logging.exception("Wata public key request failed.")
        return None

    async def _verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        public_key_pem = await self._get_public_key_pem()
        if not public_key_pem:
            return False
        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
            signature = base64.b64decode(signature_header)
            public_key.verify(signature, raw_body, padding.PKCS1v15(), hashes.SHA512())
            return True
        except (InvalidSignature, ValueError, TypeError):
            logging.warning("Wata webhook: invalid signature.")
            return False
        except Exception:
            logging.exception("Wata webhook: signature verification failed.")
            return False

    async def webhook_route(self, request: web.Request) -> web.Response:
        if not self.configured:
            return web.Response(status=503, text="wata_disabled")

        client_ip = request_client_ip(request, trusted_proxies=self.settings.trusted_proxies)
        if self.settings.wata_trusted_ips and not ip_in_allowlist(
            client_ip, self.settings.wata_trusted_ips
        ):
            logging.warning("Wata webhook denied from unauthorized IP source.")
            return web.Response(status=403, text="forbidden")

        raw_body = await request.read()
        if self.verify_webhook_signature:
            signature = request.headers.get("X-Signature", "")
            if not await self._verify_signature(raw_body, signature):
                return web.Response(status=403, text="invalid_signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            logging.exception("Wata webhook: failed to parse JSON.")
            return web.Response(status=400, text="bad_request")

        transaction_id = str(payload.get("transactionId") or "").strip()
        status = str(payload.get("transactionStatus") or "").strip().lower()
        order_id_raw = payload.get("orderId")
        amount_raw = payload.get("amount")
        currency = payload.get("currency") or self.settings.DEFAULT_CURRENCY_SYMBOL or "RUB"

        if not status or not (transaction_id or order_id_raw):
            logging.error("Wata webhook: missing transaction status or ids: %s", payload)
            return web.Response(status=400, text="missing_fields")

        payment_db_id: Optional[int] = None
        if isinstance(order_id_raw, int):
            payment_db_id = order_id_raw
        elif isinstance(order_id_raw, str) and order_id_raw.isdigit():
            payment_db_id = int(order_id_raw)

        async with self.async_session_factory() as session:
            payment = None
            if payment_db_id is not None:
                payment = await payment_dal.get_payment_by_db_id(session, payment_db_id)
            if not payment and transaction_id:
                payment = await payment_dal.get_payment_by_provider_payment_id(
                    session, transaction_id
                )

            if not payment:
                logging.error(
                    "Wata webhook: payment not found (order_id=%s, transaction_id=%s)",
                    order_id_raw,
                    transaction_id,
                )
                return web.Response(status=404, text="payment_not_found")

            if payment.status == "succeeded" and status == "paid":
                return web.Response(text="ok")

            if status == "paid":
                return await self._process_paid_payment(
                    session=session,
                    payment=payment,
                    transaction_id=transaction_id or str(payment.payment_id),
                    amount_raw=amount_raw,
                    currency=str(currency),
                )

            if status == "declined":
                return await self._process_declined_payment(
                    session=session,
                    payment=payment,
                    transaction_id=transaction_id or str(payment.payment_id),
                )

            logging.warning(
                "Wata webhook: unhandled status '%s' for transaction %s",
                status,
                transaction_id,
            )
            return web.Response(status=202, text="status_ignored")

    async def _process_paid_payment(
        self,
        *,
        session,
        payment,
        transaction_id: str,
        amount_raw: Any,
        currency: str,
    ) -> web.Response:
        payment_units = payment.purchased_gb or payment.subscription_duration_months or 1
        sale_mode = payment.sale_mode or (
            "traffic" if self.settings.traffic_sale_mode else "subscription"
        )
        sale_base = sale_mode.split("@", 1)[0].split("|", 1)[0]

        if amount_raw is not None:
            try:
                incoming_amount = self._format_amount(float(amount_raw))
                expected_amount = self._format_amount(float(payment.amount))
                if incoming_amount != expected_amount:
                    logging.warning(
                        "Wata webhook: amount mismatch for payment %s (expected %s, got %s)",
                        payment.payment_id,
                        expected_amount,
                        incoming_amount,
                    )
            except Exception as exc:
                logging.warning(
                    "Wata webhook: failed to compare amounts for %s: %s",
                    payment.payment_id,
                    exc,
                )

        try:
            await payment_dal.update_provider_payment_and_status(
                session,
                payment.payment_id,
                transaction_id,
                "succeeded",
            )

            activation = await self.subscription_service.activate_subscription(
                session,
                payment.user_id,
                int(payment_units) if sale_base == "subscription" else int(float(payment_units)),
                float(payment.amount),
                payment.payment_id,
                provider="wata",
                sale_mode=sale_mode,
                traffic_gb=float(payment_units)
                if sale_base in {"traffic", "traffic_package", "topup", "premium_topup"}
                else None,
            )

            referral_bonus = None
            if sale_base == "subscription":
                referral_bonus = await self.referral_service.apply_referral_bonuses_for_payment(
                    session,
                    payment.user_id,
                    int(payment_units),
                    current_payment_db_id=payment.payment_id,
                    skip_if_active_before_payment=False,
                )

            await session.commit()
        except Exception:
            await session.rollback()
            logging.exception("Wata webhook: failed to process payment %s.", transaction_id)
            return web.Response(status=500, text="processing_error")

        await self._notify_success(
            session=session,
            payment=payment,
            payment_units=payment_units,
            sale_base=sale_base,
            activation=activation,
            referral_bonus=referral_bonus,
            currency=currency,
        )
        return web.Response(text="ok")

    async def _process_declined_payment(self, *, session, payment, transaction_id: str):
        try:
            await payment_dal.update_provider_payment_and_status(
                session,
                payment.payment_id,
                transaction_id,
                "failed",
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logging.exception("Wata webhook: failed to mark payment %s as failed.", transaction_id)
            return web.Response(status=500, text="processing_error")

        db_user = payment.user or await user_dal.get_user_by_id(session, payment.user_id)
        lang = (
            db_user.language_code
            if db_user and db_user.language_code
            else self.settings.DEFAULT_LANGUAGE
        )
        _ = lambda k, **kw: self.i18n.gettext(lang, k, **kw) if self.i18n else k
        try:
            await self.bot.send_message(payment.user_id, _("payment_failed"))
        except Exception:
            logging.exception("Wata webhook: failed to notify user about failed payment.")
        return web.Response(text="ok")

    async def _notify_success(
        self,
        *,
        session,
        payment,
        payment_units: float,
        sale_base: str,
        activation: Optional[Dict[str, Any]],
        referral_bonus: Optional[Dict[str, Any]],
        currency: str,
    ) -> None:
        db_user = payment.user or await user_dal.get_user_by_id(session, payment.user_id)
        lang = (
            db_user.language_code
            if db_user and db_user.language_code
            else self.settings.DEFAULT_LANGUAGE
        )
        _ = lambda k, **kw: self.i18n.gettext(lang, k, **kw) if self.i18n else k

        raw_config_link = activation.get("subscription_url") if activation else None
        config_link_display, connect_button_url = await prepare_config_links(
            self.settings,
            raw_config_link,
        )
        config_link_text = config_link_display or _("config_link_not_available")
        final_end = activation.get("end_date") if activation else None
        applied_days = 0
        applied_promo_days = activation.get("applied_promo_bonus_days", 0) if activation else 0

        if referral_bonus and referral_bonus.get("referee_new_end_date"):
            final_end = referral_bonus["referee_new_end_date"]
            applied_days = referral_bonus.get("referee_bonus_applied_days", 0)

        units_label = (
            str(int(payment_units)) if float(payment_units).is_integer() else f"{payment_units:g}"
        )

        if sale_base in {"traffic", "traffic_package", "topup", "premium_topup"}:
            text = _(
                "payment_successful_traffic_full",
                traffic_gb=units_label,
                end_date=final_end.strftime("%Y-%m-%d") if final_end else "",
                config_link=config_link_text,
            )
        elif applied_days:
            inviter_name_display = _("friend_placeholder")
            if db_user and db_user.referred_by_id:
                inviter = await user_dal.get_user_by_id(session, db_user.referred_by_id)
                if inviter:
                    safe_name = (
                        sanitize_display_name(inviter.first_name)
                        if inviter.first_name
                        else None
                    )
                    if safe_name:
                        inviter_name_display = safe_name
                    elif inviter.username:
                        inviter_name_display = username_for_display(
                            inviter.username,
                            with_at=False,
                        )

            text = _(
                "payment_successful_with_referral_bonus_full",
                months=payment_units,
                base_end_date=activation["end_date"].strftime("%Y-%m-%d")
                if activation and activation.get("end_date")
                else final_end.strftime("%Y-%m-%d")
                if final_end
                else "",
                bonus_days=applied_days,
                final_end_date=final_end.strftime("%Y-%m-%d") if final_end else "",
                inviter_name=inviter_name_display,
                config_link=config_link_text,
            )
        elif applied_promo_days and final_end:
            text = _(
                "payment_successful_with_promo_full",
                months=payment_units,
                bonus_days=applied_promo_days,
                end_date=final_end.strftime("%Y-%m-%d"),
                config_link=config_link_text,
            )
        else:
            text = _(
                "payment_successful_full",
                months=payment_units,
                end_date=final_end.strftime("%Y-%m-%d") if final_end else "",
                config_link=config_link_text,
            )

        markup = get_connect_and_main_keyboard(
            lang,
            self.i18n,
            self.settings,
            config_link_display,
            connect_button_url=connect_button_url,
            preserve_message=True,
        )
        try:
            await self.bot.send_message(
                payment.user_id,
                text,
                reply_markup=markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            logging.exception("Wata webhook: failed to notify user %s.", payment.user_id)

        try:
            notification_service = NotificationService(self.bot, self.settings, self.i18n)
            await notification_service.notify_payment_received(
                user_id=payment.user_id,
                amount=float(payment.amount),
                currency=currency,
                months=int(payment_units) if sale_base == "subscription" else 0,
                traffic_gb=float(payment_units)
                if sale_base in {"traffic", "traffic_package", "topup", "premium_topup"}
                else None,
                payment_provider="wata",
                username=db_user.username if db_user else None,
                traffic_is_premium=sale_base == "premium_topup",
                tariff_key=getattr(payment, "tariff_key", None),
            )
        except Exception:
            logging.exception("Wata webhook: failed to notify admins.")


async def wata_webhook_route(request: web.Request) -> web.Response:
    service: WataService = request.app["wata_service"]
    return await service.webhook_route(request)
