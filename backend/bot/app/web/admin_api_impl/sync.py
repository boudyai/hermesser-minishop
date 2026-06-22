# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405

register_contract(
    "admin_sync_route",
    RouteContract(response_schema=ok_envelope_with({"result": loose_object_schema()})),
)


async def admin_sync_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    settings: Settings = request.app["settings"]
    queued = await enqueue_webhook_event(
        settings,
        "panel_sync",
        {"requested_by": _require_admin_user_id(request)},
        event_id=None,
    )
    if queued:
        return _ok({"result": {"status": "queued"}})
    return _error(503, "queue_unavailable")
