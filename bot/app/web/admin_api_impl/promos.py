# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


async def admin_promos_list_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    async_session_factory: sessionmaker = request.app["async_session_factory"]
    page = max(0, int(request.query.get("page", 0) or 0))
    page_size = min(100, max(1, int(request.query.get("page_size", 25) or 25)))
    async with async_session_factory() as session:
        promos = await promo_code_dal.get_all_promo_codes_with_details(
            session, limit=page_size, offset=page * page_size
        )
        total = await promo_code_dal.get_promo_codes_count(session)
    return _ok(
        {
            "promos": [_serialize_promo(p) for p in promos],
            "page": page,
            "page_size": page_size,
            "total": int(total or 0),
        }
    )


async def admin_promo_create_route(request: web.Request) -> web.Response:
    actor_id = _require_admin_user_id(request)
    payload = await _read_json(request)
    code = str(payload.get("code") or "").strip().upper()
    bonus_days = int(payload.get("bonus_days") or 0)
    max_activations = int(payload.get("max_activations") or 0)
    valid_days = payload.get("valid_days")
    if not code or bonus_days <= 0 or max_activations <= 0:
        return _error(400, "invalid_payload")

    valid_until = None
    if valid_days:
        try:
            valid_until = datetime.now(timezone.utc) + timedelta(days=int(valid_days))
        except (TypeError, ValueError):
            return _error(400, "invalid_valid_days")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        existing = await promo_code_dal.get_promo_code_by_code(session, code)
        if existing:
            return _error(409, "duplicate_code")
        promo = await promo_code_dal.create_promo_code(
            session,
            {
                "code": code,
                "bonus_days": bonus_days,
                "max_activations": max_activations,
                "valid_until": valid_until,
                "created_by_admin_id": actor_id,
                "is_active": True,
            },
        )
        await session.commit()
    return _ok({"promo": _serialize_promo(promo)})


async def admin_promo_update_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    promo_id = int(request.match_info["promo_id"])
    payload = await _read_json(request)
    update_data: Dict[str, Any] = {}
    if "is_active" in payload:
        update_data["is_active"] = bool(payload["is_active"])
    if "bonus_days" in payload and payload["bonus_days"] is not None:
        update_data["bonus_days"] = int(payload["bonus_days"])
    if "max_activations" in payload and payload["max_activations"] is not None:
        update_data["max_activations"] = int(payload["max_activations"])

    if not update_data:
        return _error(400, "no_changes")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        promo = await promo_code_dal.update_promo_code(session, promo_id, update_data)
        if not promo:
            return _error(404, "not_found")
        await session.commit()
        await session.refresh(promo)
    return _ok({"promo": _serialize_promo(promo)})


async def admin_promo_delete_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    promo_id = int(request.match_info["promo_id"])
    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        promo = await promo_code_dal.delete_promo_code(session, promo_id)
        if not promo:
            return _error(404, "not_found")
        await session.commit()
    return _ok({})
