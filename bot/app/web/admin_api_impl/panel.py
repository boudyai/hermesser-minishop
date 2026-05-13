# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


async def admin_panel_internal_squads_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    panel_service = request.app.get("panel_service")
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
        items.append(
            {
                "uuid": str(uuid),
                "name": squad.get("name") or squad.get("title") or str(uuid),
                "members_count": squad.get("membersCount")
                or squad.get("usersCount")
                or squad.get("members_count"),
                "active_inbounds_count": squad.get("activeInboundsCount")
                or squad.get("active_inbounds_count"),
            }
        )
    return _ok({"squads": items})
