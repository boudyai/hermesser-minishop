# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


async def admin_ads_list_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        campaigns = await ad_dal.list_campaigns(session)
        totals = await ad_dal.get_totals(session)
        results = []
        for campaign in campaigns:
            try:
                stats = await ad_dal.get_campaign_stats(session, campaign.ad_campaign_id)
            except Exception:
                stats = {}
            results.append(_serialize_ad(campaign, stats))
    return _ok({"campaigns": results, "totals": totals})


async def admin_ad_create_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    payload = await _read_json(request)
    source = str(payload.get("source") or "").strip()
    start_param = str(payload.get("start_param") or "").strip()
    cost = float(payload.get("cost") or 0.0)
    if not source or not start_param:
        return _error(400, "invalid_payload")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        existing = await ad_dal.get_campaign_by_start_param(session, start_param)
        if existing:
            return _error(409, "duplicate_start_param")
        campaign = await ad_dal.create_campaign(
            session,
            source=source,
            start_param=start_param,
            cost=cost,
        )
        await session.commit()
        await session.refresh(campaign)
    return _ok({"campaign": _serialize_ad(campaign)})


async def admin_ad_toggle_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    campaign_id = int(request.match_info["campaign_id"])
    payload = await _read_json(request)
    is_active = bool(payload.get("is_active", True))
    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        ok = await ad_dal.toggle_campaign_active(session, campaign_id, is_active)
        if not ok:
            return _error(404, "not_found")
        await session.commit()
    return _ok({})


async def admin_ad_delete_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    campaign_id = int(request.match_info["campaign_id"])
    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        ok = await ad_dal.delete_campaign(session, campaign_id)
        if not ok:
            return _error(404, "not_found")
        await session.commit()
    return _ok({})
