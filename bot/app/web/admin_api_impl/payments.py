# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


async def admin_payments_list_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    async_session_factory: sessionmaker = request.app["async_session_factory"]

    page = max(0, int(request.query.get("page", 0) or 0))
    page_size = min(100, max(1, int(request.query.get("page_size", 25) or 25)))

    async with async_session_factory() as session:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(Payment)
            .options(selectinload(Payment.user))
            .order_by(Payment.created_at.desc())
            .offset(page * page_size)
            .limit(page_size)
        )
        rows = (await session.execute(stmt)).scalars().all()
        total = await payment_dal.get_payments_count(session)

    return _ok(
        {
            "payments": [_serialize_payment(p) for p in rows],
            "page": page,
            "page_size": page_size,
            "total": int(total or 0),
        }
    )


async def admin_payments_export_route(request: web.Request) -> web.Response:
    _require_admin_user_id(request)
    async_session_factory: sessionmaker = request.app["async_session_factory"]

    async with async_session_factory() as session:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(Payment)
            .options(selectinload(Payment.user))
            .order_by(Payment.created_at.desc())
            .limit(10000)
        )
        rows = (await session.execute(stmt)).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "payment_id",
            "user_id",
            "user_label",
            "provider",
            "provider_payment_id",
            "amount",
            "currency",
            "status",
            "description",
            "duration_months",
            "sale_mode",
            "tariff_key",
            "created_at",
        ]
    )
    for p in rows:
        label = _payment_user_display_label(p.user, int(p.user_id)) if p.user else str(p.user_id)
        writer.writerow(
            [
                p.payment_id,
                p.user_id,
                label,
                p.provider,
                p.provider_payment_id or "",
                p.amount,
                p.currency,
                p.status,
                p.description or "",
                p.subscription_duration_months or "",
                p.sale_mode or "",
                p.tariff_key or "",
                p.created_at.isoformat() if p.created_at else "",
            ]
        )

    response = web.Response(
        body=buffer.getvalue().encode("utf-8-sig"),
        content_type="text/csv",
        charset="utf-8",
    )
    response.headers["Content-Disposition"] = 'attachment; filename="payments.csv"'
    return response
