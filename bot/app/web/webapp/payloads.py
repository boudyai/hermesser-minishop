# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


class WebAppEmailPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_and_limit_email(cls, value: EmailStr) -> str:
        normalized = normalize_email(str(value))
        if len(normalized) > 254:
            raise ValueError("email_too_long")
        return normalized


class WebAppEmailCodePayload(WebAppEmailPayload):
    code: str = ""


class WebAppEmailMagicPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: constr(min_length=8, max_length=512)


class WebAppPaymentCreatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    method: str = ""
    months: Any = None
    traffic_gb: Any = None
    device_count: Any = None
    tariff_key: Optional[constr(max_length=128)] = None
    sale_mode: Optional[constr(max_length=64)] = None
    description: Optional[constr(max_length=4096)] = None
    comment: Optional[constr(max_length=4096)] = None
    note: Optional[constr(max_length=4096)] = None


class WebAppTariffChangePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tariff_key: constr(min_length=1, max_length=128)
    mode: constr(min_length=1, max_length=64)


class WebAppLanguagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: constr(min_length=2, max_length=16)


class WebAppDeviceDisconnectPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: constr(min_length=8, max_length=128)
