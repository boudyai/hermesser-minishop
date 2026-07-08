from typing import Annotated, Any, Literal, Optional, cast

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

from bot.services.email_auth_service import normalize_email

PasswordAuthString = Annotated[str, StringConstraints(min_length=1, max_length=128)]
PasswordSetupString = Annotated[str, StringConstraints(min_length=8, max_length=128)]
ShortCodeString = Annotated[str, StringConstraints(min_length=1, max_length=32)]
MagicTokenString = Annotated[str, StringConstraints(min_length=8, max_length=512)]
TariffKeyString = Annotated[str, StringConstraints(min_length=1, max_length=128)]
OptionalTariffKeyString = Annotated[str, StringConstraints(max_length=128)]
SaleModeString = Annotated[str, StringConstraints(max_length=64)]
LongTextString = Annotated[str, StringConstraints(max_length=4096)]
BotTokenString = Annotated[str, StringConstraints(min_length=10, max_length=256)]
ChangeModeString = Annotated[str, StringConstraints(min_length=1, max_length=64)]
LanguageString = Annotated[str, StringConstraints(min_length=2, max_length=16)]
DeviceTokenString = Annotated[str, StringConstraints(min_length=8, max_length=128)]
TicketSubjectString = Annotated[str, StringConstraints(min_length=1, max_length=160)]
TicketBodyString = Annotated[str, StringConstraints(min_length=1, max_length=4000)]


class WebAppEmailPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_and_limit_email(cls, value: EmailStr) -> str:
        normalized = normalize_email(str(value))
        if len(normalized) > 254:
            raise ValueError("email_too_long")
        return cast(str, normalized)


class WebAppEmailCodePayload(WebAppEmailPayload):
    code: str = ""


class WebAppEmailRequestPayload(WebAppEmailPayload):
    language: Optional[str] = None
    referral_code: Optional[str] = None
    start_param: Optional[str] = None


class WebAppEmailCodeAuthPayload(WebAppEmailCodePayload):
    referral_code: Optional[str] = None
    start_param: Optional[str] = None


class WebAppEmailPasswordPayload(WebAppEmailPayload):
    password: PasswordAuthString


class WebAppSetPasswordPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    password: PasswordSetupString
    password_confirm: PasswordSetupString
    code: ShortCodeString


class WebAppEmailMagicPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: MagicTokenString


class WebAppEmailMagicAuthPayload(WebAppEmailMagicPayload):
    referral_code: Optional[str] = None
    start_param: Optional[str] = None


class WebAppTelegramAuthPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    init_data: str = ""
    id_token: str = ""
    nonce: str = ""
    auth_data: Any = None
    referral_code: Optional[str] = None
    start_param: Optional[str] = None


class WebAppPromoApplyPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: Any = ""


class WebAppTrialActivatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bot_token: Optional[BotTokenString] = None

    @field_validator("bot_token", mode="before")
    @classmethod
    def _strip_bot_token(cls, value: Optional[str]) -> Optional[str]:
        stripped = (value or "").strip()
        if stripped and (":" not in stripped or not stripped.split(":", 1)[0].isdigit()):
            raise ValueError("invalid_bot_token")
        return stripped or None


class WebAppEnvUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    env_content: str = ""


class WebAppCornllmTopupPayload(BaseModel):
    """Payload for a paid CornLLM (LiteLLM) budget topup.

    The amount is in rubles; the shop converts to USD (rate configured
    in ``bot.utils.currency_format.RUB_PER_USD``)
    and provisioning-core adds the delta to the tenant's active
    LitellmKey max_budget. Minimum is 100 RUB to keep payment / quota
    meaningful.
    """

    amount_rub: float
    method: str = ""

    @field_validator("amount_rub")
    @classmethod
    def _validate_amount(cls, value: float) -> float:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            raise ValueError("invalid_amount")
        if amount < 100:
            raise ValueError("amount_below_minimum")
        return round(amount, 2)


class WebAppBotTokenPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bot_token: BotTokenString


class WebAppPaymentCreatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    method: str = ""
    months: Any = None
    traffic_gb: Any = None
    device_count: Any = None
    tariff_key: Optional[OptionalTariffKeyString] = None
    sale_mode: Optional[SaleModeString] = None
    renew_hwid_devices: Optional[bool] = None
    promo_code: Optional[ShortCodeString] = None
    description: Optional[LongTextString] = None
    comment: Optional[LongTextString] = None
    note: Optional[LongTextString] = None


class WebAppPromoQuotePayload(WebAppPaymentCreatePayload):
    model_config = ConfigDict(extra="ignore")

    promo_code: ShortCodeString


class WebAppAutoRenewPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool


class WebAppTariffChangePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tariff_key: TariffKeyString
    mode: ChangeModeString


class WebAppLanguagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: LanguageString


class WebAppDeviceDisconnectPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: DeviceTokenString


SupportCategory = Literal["billing", "technical", "account", "other"]
SupportPriority = Literal["low", "normal", "high", "urgent"]
SupportStatus = Literal["open", "awaiting_user", "awaiting_admin", "resolved", "closed"]


class CreateTicketPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: TicketSubjectString
    category: SupportCategory = "other"
    priority: Literal["normal", "high"] = "normal"
    body: TicketBodyString

    @field_validator("subject", "body")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("empty_text")
        return stripped


class TicketReplyPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    body: TicketBodyString

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("empty_text")
        return stripped


class AdminTicketReplyPayload(TicketReplyPayload):
    is_internal_note: bool = False


class AdminTicketPatchPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Optional[SupportStatus] = None
    priority: Optional[SupportPriority] = None
    category: Optional[SupportCategory] = None
    assigned_admin_id: Optional[int] = None
