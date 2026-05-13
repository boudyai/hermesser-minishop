# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


async def admin_me_route(request: web.Request) -> web.Response:
    user_id = _require_admin_user_id(request)
    settings: Settings = request.app["settings"]
    return _ok({}, user_id=user_id, admin_ids=list(settings.ADMIN_IDS or []))


async def admin_stats_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    settings: Settings = request.app["settings"]
    async_session_factory: sessionmaker = request.app["async_session_factory"]

    async with async_session_factory() as session:
        user_stats = await user_dal.get_enhanced_user_statistics(session)
        financial_stats = await payment_dal.get_financial_statistics(session)
        sync_status = await panel_sync_dal.get_panel_sync_status(session)
        recent_payments = await payment_dal.get_recent_payment_logs_with_user(session, limit=10)

    payload = {
        "users": user_stats,
        "financial": financial_stats,
        "panel_sync": {
            "status": sync_status.status if sync_status else "never_run",
            "last_sync_time": sync_status.last_sync_time.isoformat()
            if sync_status and sync_status.last_sync_time
            else None,
            "details": sync_status.details if sync_status else None,
            "users_processed": sync_status.users_processed_from_panel if sync_status else 0,
            "subscriptions_synced": sync_status.subscriptions_synced if sync_status else 0,
        },
        "recent_payments": [_serialize_payment(p) for p in recent_payments],
    }

    panel_service = request.app.get("panel_service")
    if panel_service is not None:
        try:
            system = await panel_service.get_system_stats()
            bandwidth = await panel_service.get_bandwidth_stats()
            panel_body: Dict[str, Any] = {
                "system": system or {},
                "bandwidth": bandwidth or {},
            }
            try:
                nodes = await panel_service.get_nodes_statistics()
                panel_body["nodes"] = nodes or {}
            except Exception as exc_nodes:  # pragma: no cover - optional endpoint
                logger.debug("Panel nodes stats unavailable: %s", exc_nodes)
                panel_body["nodes"] = {}
            try:
                today = datetime.now(timezone.utc).date()
                start_d = today - timedelta(days=7)
                nodes_bw = await panel_service.get_nodes_bandwidth_usage(
                    start=start_d.isoformat(),
                    end=today.isoformat(),
                    top_nodes_limit=64,
                )
                panel_body["nodes_bandwidth"] = nodes_bw or {}
            except Exception as exc_nb:  # pragma: no cover - optional endpoint
                logger.debug("Panel nodes bandwidth range unavailable: %s", exc_nb)
                panel_body["nodes_bandwidth"] = {}
            try:
                online_map = _panel_nodes_online_by_uuid(panel_body.get("nodes"))
                lookups = await panel_service.get_nodes_online_lookups()
                for k, v in lookups.get("byUuid", {}).items():
                    online_map[k] = v
                _enrich_bandwidth_nodes_with_online(
                    panel_body.get("nodes_bandwidth"),
                    online_map,
                    lookups.get("byName") or {},
                )
            except Exception as exc_merge:  # pragma: no cover
                logger.debug("Panel nodes online merge skipped: %s", exc_merge)
            payload["panel"] = panel_body
        except Exception as exc:
            logger.debug("Panel stats unavailable: %s", exc)
            payload["panel"] = {"error": "unavailable"}

    queue_manager = get_queue_manager()
    if queue_manager:
        try:
            payload["queue"] = queue_manager.get_queue_stats()
        except Exception:  # pragma: no cover - defensive
            payload["queue"] = None

    payload["currency_symbol"] = settings.DEFAULT_CURRENCY_SYMBOL or "RUB"
    return _ok(payload)
