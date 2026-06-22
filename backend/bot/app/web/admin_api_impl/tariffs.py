# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405
from .webapp_runtime import refresh_webapp_runtime_after_settings_change

_TARIFFS_CONFIG_REF = {"$ref": "#/components/schemas/TariffsConfig"}
_TARIFFS_SAVE_BODY_SCHEMA = {
    "oneOf": [
        _TARIFFS_CONFIG_REF,
        {
            "type": "object",
            "additionalProperties": True,
            "required": ["catalog"],
            "properties": {"catalog": _TARIFFS_CONFIG_REF},
        },
    ]
}
_TARIFFS_RESPONSE_SCHEMA = ok_envelope_with(
    {
        "exists": BOOLEAN_SCHEMA,
        "path": STRING_SCHEMA,
        "catalog": loose_object_schema(),
        "provider_currency_support": loose_array_schema(),
    }
)

register_contract(
    "admin_tariffs_get_route",
    RouteContract(response_schema=_TARIFFS_RESPONSE_SCHEMA, models=(TariffsConfig,)),
)
register_contract(
    "admin_tariffs_save_route",
    RouteContract(
        request_schema=_TARIFFS_SAVE_BODY_SCHEMA,
        response_schema=_TARIFFS_RESPONSE_SCHEMA,
        models=(TariffsConfig,),
    ),
)


async def admin_tariffs_get_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    settings: Settings = request.app["settings"]
    path = _tariffs_config_path(settings)

    try:
        config = settings.tariffs_config
    except Exception as exc:
        logger.warning("Invalid tariffs config requested from admin UI: %s", exc)
        return _error(400, "invalid_tariffs_config", str(exc))

    if config is None:
        return _ok(
            {
                "exists": path.exists(),
                "path": str(path),
                "catalog": {
                    "default_tariff": "",
                    "default_currency": "rub",
                    "topup_packages_default": {"rub": [], "stars": []},
                    "tariffs": [],
                },
                "provider_currency_support": _provider_currency_support_payload(
                    settings,
                    request.app,
                ),
            }
        )

    return _ok(
        {
            "exists": True,
            "path": str(path),
            "catalog": _tariffs_config_payload(config),
            "provider_currency_support": _provider_currency_support_payload(settings, request.app),
        }
    )


async def admin_tariffs_save_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    settings: Settings = request.app["settings"]
    payload = await _read_json(request)
    catalog = payload.get("catalog") if "catalog" in payload else payload
    if not isinstance(catalog, dict):
        return _error(400, "invalid_payload", "catalog must be an object")

    try:
        config = TariffsConfig.model_validate(catalog)
    except (ValidationError, ValueError) as exc:
        return _error(400, "invalid_tariffs_config", str(exc))

    path = _tariffs_config_path(settings)
    try:
        _write_tariffs_config_file(path, config)
    except OSError as exc:
        logger.exception("Failed to write tariffs config to %s", path)
        return _error(500, "write_failed", str(exc))

    await refresh_webapp_runtime_after_settings_change(request, updates={}, deletes=[])

    return _ok(
        {
            "exists": True,
            "path": str(path),
            "catalog": _tariffs_config_payload(config),
            "provider_currency_support": _provider_currency_support_payload(settings, request.app),
        }
    )


def _provider_currency_support_payload(
    settings: Settings,
    app: web.Application,
) -> List[Dict[str, Any]]:
    from bot.payment_providers import iter_provider_specs, resolve_provider_presentation

    default_currency = default_payment_currency_code_for_settings(settings)
    providers: List[Dict[str, Any]] = []
    for spec in iter_provider_specs():
        presentation = resolve_provider_presentation(spec, settings)
        supported = spec.supported_currency_codes(settings)
        providers.append(
            {
                "id": spec.id,
                "provider_key": spec.provider_key,
                "provider_label": _provider_currency_support_label(spec),
                "settings_path": _provider_settings_path(spec),
                "label": presentation.webapp_label or spec.label,
                "telegram_label": presentation.telegram_label,
                "icon": presentation.webapp_icon,
                "enabled": spec.is_effectively_enabled(settings),
                "configured": spec.is_service_configured(app),
                "admin_only": spec.is_admin_only_enabled(settings),
                "price_source": spec.price_source,
                "currencies": list(supported) if supported is not None else None,
                "accepts_any_currency": supported is None,
                "supports_default_currency": spec.is_usable_for_payment_currency(
                    settings,
                    default_currency,
                ),
                "directly_supports_default_currency": spec.supports_currency(
                    settings,
                    default_currency,
                ),
                "default_currency": default_currency,
                "note": spec.currency_support_note,
                "docs_url": spec.currency_support_url,
            }
        )
    return providers


def _provider_currency_support_label(spec: Any) -> str:
    if spec.id == "platega_sbp":
        return "Platega SBP/card"
    if spec.id == "platega_crypto":
        return "Platega Crypto"
    return str(spec.label or spec.id)


def _provider_settings_path(spec: Any) -> List[str]:
    if spec.id == "platega_sbp":
        return ["payments", "platega", "sbp"]
    if spec.id == "platega_crypto":
        return ["payments", "platega", "crypto"]
    return ["payments", str(spec.provider_key or spec.id).replace("_", "-")]
