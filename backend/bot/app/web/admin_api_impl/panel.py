import logging

from aiohttp import web

from bot.app.web.context import (
    get_panel_service,
    get_settings,
)
from bot.app.web.route_contracts import (
    RouteContract,
    ok_envelope_for,
    register_contract,
)
from config.settings import Settings

from .auth import (
    _require_admin_user_id,
)
from .common import (
    _error,
    _ok,
)
from .response_schemas import AdminPanelInternalSquadOut

logger = logging.getLogger(__name__)

register_contract(
    "admin_panel_internal_squads_route",
    RouteContract(
        response_schema=ok_envelope_for(AdminPanelInternalSquadOut, key="squads", many=True),
        models=(AdminPanelInternalSquadOut,),
    ),
)


def _first_squad_value(squad: dict[str, object], *keys: str) -> int | float | str | bool | None:
    for key in keys:
        value = squad.get(key)
        if value:
            if isinstance(value, (int, float, str, bool)):
                return value
            return str(value)
    return None


async def admin_panel_internal_squads_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    settings: Settings = get_settings(request)
    # ponytail: in hermes mode the proxy-era Remnawave panel is not in
    # use and PANEL_API_URL points at provisioning-core, which has no
    # /internal-squads endpoint. Short-circuit with an empty list so
    # admin tariffs UI doesn't show "panel unavailable".
    if str(getattr(settings.panel_settings, "write_mode", "") or "").lower() == "hermes":
        return _ok({"squads": []})
    panel_service = get_panel_service(request)
    if panel_service is None:
        return _error(503, "panel_unavailable", "Panel service unavailable")
    try:
        squads = await panel_service.get_internal_squads()
    except Exception as exc:
        logger.exception("Failed to load internal squads from panel")
        return _error(502, "panel_request_failed", str(exc))
    if squads is None:
        return _error(502, "panel_request_failed", "Unable to load internal squads")
    items = []
    for squad in squads:
        if not isinstance(squad, dict):
            continue
        uuid = squad.get("uuid") or squad.get("id")
        if not uuid:
            continue
        item = AdminPanelInternalSquadOut(
            uuid=str(uuid),
            name=str(squad.get("name") or squad.get("title") or uuid),
            members_count=_first_squad_value(squad, "membersCount", "usersCount", "members_count"),
            active_inbounds_count=_first_squad_value(
                squad,
                "activeInboundsCount",
                "active_inbounds_count",
            ),
        )
        items.append(item.model_dump(mode="json"))
    return _ok({"squads": items})
