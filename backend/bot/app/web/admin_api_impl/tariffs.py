import logging
from pathlib import Path

from aiohttp import web
from pydantic import ValidationError

from bot.app.web.context import (
    get_settings,
)
from bot.app.web.request_parsing import parse_body_or_400
from bot.app.web.route_contracts import (
    RouteContract,
    ok_envelope_for,
    register_contract,
)
from bot.app.web.webapp.cache_helpers import refresh_webapp_runtime_after_settings_change
from config.settings import Settings
from config.tariffs_config import TariffsConfig, default_payment_currency_code_for_settings

from .auth import (
    _require_admin_user_id,
)
from .common import (
    _error,
    _ok,
    _tariffs_config_path,
    _write_tariffs_config_file,
)
from .schemas import (
    AdminTariffsCatalogOut,
    AdminTariffsOut,
    ProviderCurrencySupportOut,
    TariffsSaveBody,
)

logger = logging.getLogger(__name__)

_TARIFFS_RESPONSE_SCHEMA = ok_envelope_for(AdminTariffsOut)

register_contract(
    "admin_tariffs_get_route",
    RouteContract(response_schema=_TARIFFS_RESPONSE_SCHEMA, models=(AdminTariffsOut,)),
)
register_contract(
    "admin_tariffs_save_route",
    RouteContract(
        request_model=TariffsSaveBody,
        response_schema=_TARIFFS_RESPONSE_SCHEMA,
        models=(TariffsSaveBody, AdminTariffsOut),
    ),
)


async def admin_tariffs_get_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    settings: Settings = get_settings(request)
    path = _tariffs_config_path(settings)

    try:
        config = settings.tariffs_config
    except Exception as exc:
        logger.warning("Invalid tariffs config requested from admin UI: %s", exc)
        return _error(400, "invalid_tariffs_config", str(exc))

    return _ok(_tariffs_response_payload(settings, request.app, path=path, config=config))


async def admin_tariffs_save_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    settings: Settings = get_settings(request)
    body = await parse_body_or_400(request, TariffsSaveBody)
    catalog = body.catalog_payload()
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

    return _ok(_tariffs_response_payload(settings, request.app, path=path, config=config))


def _tariffs_response_payload(
    settings: Settings,
    app: web.Application,
    *,
    path: Path,
    config: TariffsConfig | None,
) -> dict[str, object]:
    catalog = (
        AdminTariffsCatalogOut.from_config(config)
        if config is not None
        else AdminTariffsCatalogOut.empty()
    )
    return AdminTariffsOut(
        exists=True if config is not None else path.exists(),
        path=str(path),
        catalog=catalog,
        provider_currency_support=_provider_currency_support_payload(settings, app),
    ).to_legacy_payload()


def _provider_currency_support_payload(
    settings: Settings,
    app: web.Application,
) -> list[ProviderCurrencySupportOut]:
    from bot.payment_providers import iter_provider_specs, resolve_provider_presentation

    default_currency = default_payment_currency_code_for_settings(settings)
    providers: list[ProviderCurrencySupportOut] = []
    for spec in iter_provider_specs():
        presentation = resolve_provider_presentation(spec, settings)
        providers.append(
            ProviderCurrencySupportOut.from_provider_spec(
                spec,
                presentation,
                settings=settings,
                app=app,
                default_currency=default_currency,
            )
        )
    return providers
