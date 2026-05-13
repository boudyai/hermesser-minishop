# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


async def admin_sync_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    panel_service = request.app.get("panel_service")
    if panel_service is None:
        return _error(503, "panel_unavailable")
    settings: Settings = request.app["settings"]
    async_session_factory: sessionmaker = request.app["async_session_factory"]
    i18n = request.app.get("i18n")

    from bot.handlers.admin.sync_admin import perform_sync

    async with async_session_factory() as session:
        result = await perform_sync(
            panel_service=panel_service,
            session=session,
            settings=settings,
            i18n_instance=i18n,
        )
    return _ok({"result": result or {}})
