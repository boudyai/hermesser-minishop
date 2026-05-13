# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


async def apply_promo_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    payload = await _read_json(request)
    code = str(payload.get("code") or "").strip()
    if not code:
        return _json_error(400, "empty_code", "Promo code is empty")

    settings: Settings = request.app["settings"]
    promo_code_service: PromoCodeService = request.app.get("promo_code_service")
    if not promo_code_service:
        return _json_error(503, "service_unavailable", "Promo service unavailable")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        try:
            db_user = await user_dal.get_user_by_id(session, user_id)
            if not db_user or db_user.is_banned:
                await session.rollback()
                return _json_error(403, "access_denied", "Access denied")
            lang = _normalize_language(db_user.language_code or settings.DEFAULT_LANGUAGE)
            success, result = await promo_code_service.apply_promo_code(
                session,
                user_id,
                code,
                lang,
            )
            if not success:
                await session.commit()
                return _json_error(400, "promo_apply_failed", str(result))
            await session.commit()
            end_date = result if isinstance(result, datetime) else None
            return web.json_response(
                {
                    "ok": True,
                    "end_date": end_date.isoformat() if end_date else None,
                    "end_date_text": end_date.strftime("%d.%m.%Y %H:%M") if end_date else None,
                }
            )
        except Exception:
            await session.rollback()
            logger.exception("WebApp promo apply failed")
            return _json_error(500, "promo_apply_failed", "Promo apply failed")


async def create_payment_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    rate_limit_response = await _enforce_webapp_rate_limit(
        request,
        user_id=user_id,
        action="payments_create",
    )
    if rate_limit_response:
        return rate_limit_response

    payload = await _read_json(request)
    payment_payload, validation_error = _validate_model_payload(WebAppPaymentCreatePayload, payload)
    if validation_error:
        return validation_error
    method = str(payment_payload.method or "").strip().lower()
    settings: Settings = request.app["settings"]
    cached = _get_cached_webapp_settings(request)
    tariffs_config = settings.tariffs_config
    traffic_mode = bool(settings.traffic_sale_mode)
    sale_mode = "subscription"
    traffic_gb_for_payment: Optional[float] = None
    requested_sale_mode = _sale_mode_base(str(payment_payload.sale_mode or ""))

    if tariffs_config and requested_sale_mode in {"hwid_device", "hwid_devices"}:
        tariff_key = str(payment_payload.tariff_key or "").strip()
        if not tariff_key:
            return _json_error(400, "invalid_plan", "Tariff is not selected")
        try:
            tariff = tariffs_config.require(tariff_key)
        except Exception:
            return _json_error(400, "invalid_plan", "Tariff is not available")
        try:
            device_count = int(
                float(
                    payment_payload.device_count
                    if payment_payload.device_count is not None
                    else payment_payload.months
                )
            )
        except (TypeError, ValueError):
            return _json_error(400, "invalid_plan", "Invalid device package")
        packages = tariff.hwid_device_packages
        rub_packages = {
            int(package.count): float(package.price)
            for package in (packages.rub if packages else [])
        }
        stars_packages = {
            int(package.count): int(float(package.price))
            for package in (packages.stars if packages else [])
        }
        price = rub_packages.get(device_count)
        stars_price = stars_packages.get(device_count)
        if price is None and method != "stars":
            return _json_error(400, "invalid_plan", "Device package is not available")
        if method == "stars" and (stars_price is None or int(stars_price) <= 0):
            return _json_error(400, "invalid_plan", "Stars price is not configured")
        payment_units = device_count
        sale_mode = f"hwid_devices@{tariff.key}"
    elif tariffs_config and requested_sale_mode in {"topup", "premium_topup"}:
        tariff_key = str(payment_payload.tariff_key or "").strip()
        if not tariff_key:
            return _json_error(400, "invalid_plan", "Tariff is not selected")
        try:
            tariff = tariffs_config.require(tariff_key)
        except Exception:
            return _json_error(400, "invalid_plan", "Tariff is not available")
        try:
            traffic_gb = float(
                payment_payload.traffic_gb
                if payment_payload.traffic_gb is not None
                else payment_payload.months
            )
        except (TypeError, ValueError):
            return _json_error(400, "invalid_plan", "Invalid traffic package")
        packages = (
            tariff.premium_topup_packages
            if requested_sale_mode == "premium_topup"
            else tariffs_config.topup_packages_for(tariff)
        )
        rub_packages = {
            float(package.gb): float(package.price)
            for package in (packages.rub if packages else [])
        }
        stars_packages = {
            float(package.gb): int(float(package.price))
            for package in (packages.stars if packages else [])
        }
        package_key = _resolve_numeric_option_key(rub_packages, traffic_gb)
        stars_package_key = _resolve_numeric_option_key(stars_packages, traffic_gb)
        price = rub_packages.get(package_key) if package_key is not None else None
        stars_price = (
            stars_packages.get(stars_package_key) if stars_package_key is not None else None
        )
        if price is None and method != "stars":
            return _json_error(400, "invalid_plan", "Traffic package is not available")
        if method == "stars" and (stars_price is None or int(stars_price) <= 0):
            return _json_error(400, "invalid_plan", "Stars price is not configured")
        payment_units = int(traffic_gb) if float(traffic_gb).is_integer() else traffic_gb
        traffic_gb_for_payment = float(payment_units)
        sale_mode = f"{requested_sale_mode}@{tariff.key}"
    elif tariffs_config:
        tariff_key = str(payment_payload.tariff_key or "").strip()
        if not tariff_key:
            return _json_error(400, "invalid_plan", "Tariff is not selected")
        try:
            tariff = tariffs_config.require(tariff_key)
        except Exception:
            return _json_error(400, "invalid_plan", "Tariff is not available")

        if tariff.billing_model == "traffic":
            try:
                traffic_gb = float(
                    payment_payload.traffic_gb
                    if payment_payload.traffic_gb is not None
                    else payment_payload.months
                )
            except (TypeError, ValueError):
                return _json_error(400, "invalid_plan", "Invalid traffic package")
            if traffic_gb <= 0:
                return _json_error(400, "invalid_plan", "Invalid traffic package")
            rub_packages = {
                float(package.gb): float(package.price)
                for package in (tariff.traffic_packages.rub if tariff.traffic_packages else [])
            }
            stars_packages = {
                float(package.gb): int(float(package.price))
                for package in (tariff.traffic_packages.stars if tariff.traffic_packages else [])
            }
            package_key = _resolve_numeric_option_key(rub_packages, traffic_gb)
            stars_package_key = _resolve_numeric_option_key(stars_packages, traffic_gb)
            price = rub_packages.get(package_key) if package_key is not None else None
            stars_price = (
                stars_packages.get(stars_package_key) if stars_package_key is not None else None
            )
            if price is None and method != "stars":
                return _json_error(400, "invalid_plan", "Traffic package is not available")
            if method == "stars" and (stars_price is None or int(stars_price) <= 0):
                return _json_error(400, "invalid_plan", "Stars price is not configured")
            payment_units = int(traffic_gb) if float(traffic_gb).is_integer() else traffic_gb
            traffic_gb_for_payment = float(payment_units)
            sale_mode = f"traffic_package@{tariff.key}"
        else:
            try:
                months = int(float(payment_payload.months))
            except (TypeError, ValueError):
                return _json_error(400, "invalid_plan", "Invalid subscription period")
            if months not in tariff.enabled_periods:
                return _json_error(400, "invalid_plan", "Subscription period is not available")
            price = tariff.period_price(months, "rub")
            stars_price_raw = tariff.period_price(months, "stars")
            stars_price = int(stars_price_raw) if stars_price_raw and stars_price_raw > 0 else None
            if price is None and method != "stars":
                return _json_error(400, "invalid_plan", "Subscription period is not available")
            if method == "stars" and (stars_price is None or int(stars_price) <= 0):
                return _json_error(400, "invalid_plan", "Stars price is not configured")
            payment_units = months
            sale_mode = f"subscription@{tariff.key}"
    elif traffic_mode:
        try:
            traffic_gb = float(
                payment_payload.traffic_gb
                if payment_payload.traffic_gb is not None
                else payment_payload.months
            )
        except (TypeError, ValueError):
            return _json_error(400, "invalid_plan", "Invalid traffic package")
        if traffic_gb <= 0:
            return _json_error(400, "invalid_plan", "Invalid traffic package")
        package_key = _resolve_numeric_option_key(cached["traffic_packages"], traffic_gb)
        stars_package_key = _resolve_numeric_option_key(
            cached["stars_traffic_packages"], traffic_gb
        )
        price = cached["traffic_packages"].get(package_key) if package_key is not None else None
        stars_price = (
            cached["stars_traffic_packages"].get(stars_package_key)
            if stars_package_key is not None
            else None
        )
        if price is None and method != "stars":
            return _json_error(400, "invalid_plan", "Traffic package is not available")
        if method == "stars" and (stars_price is None or int(stars_price) <= 0):
            return _json_error(400, "invalid_plan", "Stars price is not configured")
        payment_units = int(traffic_gb) if float(traffic_gb).is_integer() else traffic_gb
        traffic_gb_for_payment = float(payment_units)
        sale_mode = "traffic"
    else:
        try:
            months = int(float(payment_payload.months))
        except (TypeError, ValueError):
            return _json_error(400, "invalid_plan", "Invalid subscription period")
        price = cached["subscription_options"].get(months)
        stars_price = cached["stars_subscription_options"].get(months)
        if price is None and method != "stars":
            return _json_error(400, "invalid_plan", "Subscription period is not available")
        if method == "stars" and (stars_price is None or int(stars_price) <= 0):
            return _json_error(400, "invalid_plan", "Stars price is not configured")
        payment_units = months
        sale_mode = "subscription"

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")
        lang = db_user.language_code or settings.DEFAULT_LANGUAGE
        return await _create_subscription_payment(
            request=request,
            session=session,
            user_id=user_id,
            method=method,
            months=payment_units,
            price=float(price or 0),
            stars_price=stars_price,
            lang=lang,
            sale_mode=sale_mode,
            traffic_gb=traffic_gb_for_payment,
        )


async def activate_trial_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    rate_limit_response = await _enforce_webapp_rate_limit(
        request,
        user_id=user_id,
        action="trial_activate",
    )
    if rate_limit_response:
        return rate_limit_response

    settings: Settings = request.app["settings"]
    if not settings.TRIAL_ENABLED or settings.TRIAL_DURATION_DAYS <= 0:
        return _json_error(400, "trial_unavailable", "Trial is not available")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    subscription_service: SubscriptionService = request.app["subscription_service"]
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")

        activation_result = await subscription_service.activate_trial_subscription(session, user_id)
        if not activation_result or not activation_result.get("activated"):
            await session.rollback()
            message_key = (
                activation_result.get("message_key", "trial_activation_failed")
                if activation_result
                else "trial_activation_failed"
            )
            status = 400 if message_key != "trial_activation_failed_panel_update" else 502
            return _json_error(status, message_key, message_key)

        end_date = activation_result.get("end_date")
        config_link, connect_url = await prepare_config_links(
            settings,
            activation_result.get("subscription_url"),
        )

        i18n_instance = request.app.get("i18n")
        if settings.LOG_TRIAL_ACTIVATIONS and i18n_instance:
            try:
                from bot.services.notification_service import NotificationService

                notification_service = NotificationService(
                    request.app["bot"], settings, i18n_instance
                )
                await notification_service.notify_trial_activation(user_id, end_date)
            except Exception:
                logger.exception("Failed to send WebApp trial activation notification")

        try:
            from db.dal import ad_dal as _ad_dal

            await _ad_dal.mark_trial_activated(session, user_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to mark WebApp trial activation for ad attribution")

        return web.json_response(
            {
                "ok": True,
                "activated": True,
                "days": activation_result.get("days", settings.TRIAL_DURATION_DAYS),
                "end_date": end_date.isoformat() if isinstance(end_date, datetime) else None,
                "end_date_text": _format_webapp_datetime(end_date)
                if isinstance(end_date, datetime)
                else None,
                "traffic_gb": activation_result.get("traffic_gb", settings.TRIAL_TRAFFIC_LIMIT_GB),
                "config_link": config_link,
                "connect_url": connect_url or config_link,
            }
        )


async def tariff_topup_options_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    settings: Settings = request.app["settings"]
    config = settings.tariffs_config
    topup_kind = str(request.query.get("kind") or "all").strip().lower()
    if topup_kind not in {"all", "regular", "premium"}:
        return _json_error(400, "invalid_topup_kind", "Invalid topup kind")
    if not config:
        return _json_error(404, "tariffs_unavailable", "Tariffs are not configured")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")
        sub = await subscription_dal.get_active_subscription_by_user_id(
            session, user_id, db_user.panel_user_uuid
        )
        if not sub or not sub.tariff_key:
            return _json_error(
                400, "subscription_required", "Active tariff subscription is required"
            )
        lang = db_user.language_code or settings.DEFAULT_LANGUAGE
        tariff = config.require(sub.tariff_key)
        plans = (
            _serialize_topup_packages(settings, tariff, config.topup_packages_for(tariff), lang)
            if topup_kind in {"all", "regular"}
            else []
        )
        premium_plans = (
            _serialize_topup_packages(
                settings,
                tariff,
                tariff.premium_topup_packages,
                lang,
                sale_mode="premium_topup",
                title_prefix=f"{tariff.premium_name(lang)} ",
            )
            if topup_kind in {"all", "premium"} and tariff.premium_squad_uuids
            else []
        )
        premium_bonus_bytes = int(getattr(sub, "premium_bonus_bytes", 0) or 0)
        premium_unlimited_override = bool(getattr(sub, "premium_unlimited_override", False))
        premium_limit_bytes = (
            int(sub.premium_baseline_bytes or 0)
            + int(sub.premium_topup_balance_bytes or 0)
            + int(getattr(sub, "premium_topup_used_bytes", 0) or 0)
            + premium_bonus_bytes
        )
        premium_access = await request.app["subscription_service"].premium_access_for_tariff(tariff)
        return web.json_response(
            {
                "ok": True,
                "tariff_key": tariff.key,
                "tariff_name": tariff.name(lang),
                "topup_kind": topup_kind,
                "premium_title": tariff.premium_name(lang),
                "traffic_percent": _traffic_percent(
                    sub.traffic_used_bytes, sub.traffic_limit_bytes
                ),
                "premium_traffic_percent": 0
                if premium_unlimited_override
                else _traffic_percent(
                    sub.premium_used_bytes,
                    premium_limit_bytes,
                ),
                "premium_limit_bytes": premium_limit_bytes,
                "premium_used_bytes": int(sub.premium_used_bytes or 0),
                "premium_baseline_bytes": int(sub.premium_baseline_bytes or 0),
                "premium_topup_balance_bytes": int(sub.premium_topup_balance_bytes or 0),
                "premium_topup_used_bytes": int(getattr(sub, "premium_topup_used_bytes", 0) or 0),
                "premium_bonus_bytes": premium_bonus_bytes,
                "premium_unlimited_override": premium_unlimited_override,
                "premium_is_limited": bool(sub.premium_is_limited),
                "premium_squad_labels": premium_access.get("squad_labels") or [],
                "premium_node_labels": premium_access.get("node_labels") or [],
                "warning_levels": settings.tariff_traffic_warning_levels,
                "plans": plans + premium_plans,
            }
        )


async def tariff_change_options_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    settings: Settings = request.app["settings"]
    config = settings.tariffs_config
    if not config:
        return _json_error(404, "tariffs_unavailable", "Tariffs are not configured")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    subscription_service: SubscriptionService = request.app["subscription_service"]
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")
        sub = await subscription_dal.get_active_subscription_by_user_id(
            session, user_id, db_user.panel_user_uuid
        )
        if not sub or not sub.tariff_key:
            return _json_error(
                400, "subscription_required", "Active tariff subscription is required"
            )
        lang = db_user.language_code or settings.DEFAULT_LANGUAGE
        current = config.require(sub.tariff_key)
        targets = []
        for tariff in config.enabled_tariffs:
            if tariff.key == current.key:
                continue
            options = subscription_service.calculate_tariff_switch_options(sub, tariff)
            targets.append(_serialize_tariff_change_target(settings, config, tariff, options, lang))
        return web.json_response(
            {
                "ok": True,
                "current": {
                    "tariff_key": current.key,
                    "title": current.name(lang),
                    "description": current.description(lang),
                    "billing_model": current.billing_model,
                },
                "targets": targets,
            }
        )


async def tariff_change_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    payload = await _read_json(request)
    change_payload, validation_error = _validate_model_payload(WebAppTariffChangePayload, payload)
    if validation_error:
        return validation_error
    mode = str(change_payload.mode or "").strip()
    if mode not in {"recalc_days", "convert_days_to_gb"}:
        return _json_error(400, "invalid_change_mode", "This tariff change requires payment")

    settings: Settings = request.app["settings"]
    if not settings.tariffs_config:
        return _json_error(404, "tariffs_unavailable", "Tariffs are not configured")
    async_session_factory: sessionmaker = request.app["async_session_factory"]
    subscription_service: SubscriptionService = request.app["subscription_service"]
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")
        result = await subscription_service.switch_tariff_without_payment(
            session,
            user_id,
            str(change_payload.tariff_key),
            mode,
        )
        if not result:
            await session.rollback()
            return _json_error(400, "change_failed", "Tariff change failed")
        await session.commit()
        return web.json_response({"ok": True, **result})


async def tariff_change_payment_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    payload = await _read_json(request)
    payment_payload, validation_error = _validate_model_payload(WebAppPaymentCreatePayload, payload)
    if validation_error:
        return validation_error
    method = str(payment_payload.method or "").strip().lower()
    tariff_key = str(payment_payload.tariff_key or "").strip()
    settings: Settings = request.app["settings"]
    config = settings.tariffs_config
    if not config:
        return _json_error(404, "tariffs_unavailable", "Tariffs are not configured")
    if not tariff_key:
        return _json_error(400, "invalid_plan", "Tariff is not selected")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    subscription_service: SubscriptionService = request.app["subscription_service"]
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")
        sub = await subscription_dal.get_active_subscription_by_user_id(
            session, user_id, db_user.panel_user_uuid
        )
        if not sub:
            return _json_error(
                400, "subscription_required", "Active tariff subscription is required"
            )
        target = config.require(tariff_key)
        options = subscription_service.calculate_tariff_switch_options(sub, target)
        price = float(options.get("paid_diff_rub") or 0)
        if price <= 0:
            return _json_error(
                400, "payment_not_required", "Payment is not required for this tariff change"
            )
        return await _create_subscription_payment(
            request=request,
            session=session,
            user_id=user_id,
            method=method,
            months=1,
            price=price,
            stars_price=None,
            lang=db_user.language_code or settings.DEFAULT_LANGUAGE,
            sale_mode=f"tariff_upgrade@{target.key}",
        )


async def device_topup_options_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    settings: Settings = request.app["settings"]
    config = settings.tariffs_config
    if not settings.MY_DEVICES_SECTION_ENABLED:
        return _json_error(404, "devices_disabled", "Devices section is disabled")
    if not config:
        return _json_error(404, "tariffs_unavailable", "Tariffs are not configured")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    subscription_service: SubscriptionService = request.app["subscription_service"]
    async with async_session_factory() as session:
        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or db_user.is_banned:
            return _json_error(403, "access_denied", "Access denied")
        sub = await subscription_dal.get_active_subscription_by_user_id(
            session, user_id, db_user.panel_user_uuid
        )
        if not sub or not sub.tariff_key:
            return _json_error(
                400, "subscription_required", "Active tariff subscription is required"
            )
        tariff = config.require(sub.tariff_key)
        active = await subscription_service.get_active_subscription_details(session, user_id)
        plans = _serialize_hwid_device_packages(
            settings,
            tariff,
            tariff.hwid_device_packages,
            db_user.language_code or settings.DEFAULT_LANGUAGE,
        )
        return web.json_response(
            {
                "ok": True,
                "tariff_key": tariff.key,
                "tariff_name": tariff.name(db_user.language_code or settings.DEFAULT_LANGUAGE),
                "current_limit": _coerce_int_or_none(active.get("max_devices")) if active else None,
                "extra_hwid_devices": int(sub.extra_hwid_devices or 0),
                "plans": plans,
            }
        )


async def payment_status_route(request: web.Request) -> web.Response:
    user_id = _require_user_id(request)
    try:
        payment_id = int(request.match_info["payment_id"])
    except (TypeError, ValueError):
        return _json_error(400, "invalid_payment", "Invalid payment id")

    async_session_factory: sessionmaker = request.app["async_session_factory"]
    async with async_session_factory() as session:
        payment = await payment_dal.get_payment_by_db_id(session, payment_id)
        if not payment or payment.user_id != user_id:
            return _json_error(404, "not_found", "Payment not found")
        return web.json_response(
            {
                "ok": True,
                "payment_id": payment.payment_id,
                "status": payment.status,
                "paid": payment.status == "succeeded",
            }
        )


def _sale_mode_base(sale_mode: str) -> str:
    return str(sale_mode or "subscription").split("@", 1)[0].split("|", 1)[0]


def _sale_mode_tariff_key(sale_mode: str) -> Optional[str]:
    if "@" not in str(sale_mode or ""):
        return None
    return str(sale_mode).split("@", 1)[1].split("|", 1)[0] or None


def _sale_mode_is_traffic(sale_mode: str) -> bool:
    return _sale_mode_base(sale_mode) in {"traffic", "traffic_package", "topup", "premium_topup"}


def _sale_mode_is_hwid_devices(sale_mode: str) -> bool:
    return _sale_mode_base(sale_mode) in {"hwid_device", "hwid_devices"}


async def _create_subscription_payment(
    *,
    request: web.Request,
    session: AsyncSession,
    user_id: int,
    method: str,
    months: Any,
    price: float,
    stars_price: Optional[int],
    lang: str,
    sale_mode: str = "subscription",
    traffic_gb: Optional[float] = None,
) -> web.Response:
    settings: Settings = request.app["settings"]
    sale_mode = str(sale_mode or "subscription")
    traffic_sale = _sale_mode_is_traffic(sale_mode)
    hwid_devices_sale = _sale_mode_is_hwid_devices(sale_mode)
    description = (
        _traffic_payment_description(float(traffic_gb if traffic_gb is not None else months), lang)
        if traffic_sale
        else _hwid_devices_payment_description(int(float(months)), lang)
        if hwid_devices_sale
        else _payment_description(int(months), lang)
    )

    if method == "yookassa":
        if not settings.YOOKASSA_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        return await _create_yookassa_payment(
            request,
            session,
            user_id,
            months,
            price,
            description,
            sale_mode=sale_mode,
            traffic_gb=traffic_gb,
        )
    if method == "freekassa":
        if not settings.FREEKASSA_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        return await _create_freekassa_payment(
            request,
            session,
            user_id,
            months,
            price,
            description,
            sale_mode=sale_mode,
            traffic_gb=traffic_gb,
        )
    if method in ("platega", "platega_sbp", "platega_crypto"):
        if not settings.PLATEGA_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        if method == "platega_sbp" and not settings.PLATEGA_SBP_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        if method == "platega_crypto" and not settings.PLATEGA_CRYPTO_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        return await _create_platega_payment(
            request,
            session,
            user_id,
            months,
            price,
            description,
            variant=method,
            sale_mode=sale_mode,
            traffic_gb=traffic_gb,
        )
    if method == "severpay":
        if not settings.SEVERPAY_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        return await _create_severpay_payment(
            request,
            session,
            user_id,
            months,
            price,
            description,
            sale_mode=sale_mode,
            traffic_gb=traffic_gb,
        )
    if method == "cryptopay":
        service: CryptoPayService = request.app["cryptopay_service"]
        if not settings.CRYPTOPAY_ENABLED or not service or not service.configured:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        url = await service.create_invoice(
            session=session,
            user_id=user_id,
            months=months,
            amount=price,
            description=description,
            sale_mode=sale_mode,
            url_kind="web",
        )
        if not url:
            return _json_error(502, "payment_failed", "Failed to create payment")
        return web.json_response(
            {"ok": True, "action": "open_link", "payment_url": url, "payment_id": None}
        )
    if method == "stars":
        if not settings.STARS_ENABLED or stars_price is None:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        return await _create_stars_payment(
            request,
            session,
            user_id,
            months,
            int(stars_price),
            description,
            sale_mode=sale_mode,
            traffic_gb=traffic_gb,
        )

    return _json_error(400, "payment_unavailable", "Payment method unavailable")


async def _create_base_payment_record(
    session: AsyncSession,
    *,
    user_id: int,
    amount: float,
    currency: str,
    status: str,
    description: str,
    months: int,
    provider: str,
    sale_mode: Optional[str] = None,
    tariff_key: Optional[str] = None,
    purchased_gb: Optional[float] = None,
    purchased_hwid_devices: Optional[int] = None,
) -> Payment:
    payment = await payment_dal.create_payment_record(
        session,
        {
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "status": status,
            "description": description,
            "subscription_duration_months": months,
            "provider": provider,
            "sale_mode": sale_mode,
            "tariff_key": tariff_key,
            "purchased_gb": purchased_gb,
            "purchased_hwid_devices": purchased_hwid_devices,
        },
    )
    await session.commit()
    return payment


async def _create_yookassa_payment(
    request: web.Request,
    session: AsyncSession,
    user_id: int,
    months: Any,
    price: float,
    description: str,
    *,
    sale_mode: str = "subscription",
    traffic_gb: Optional[float] = None,
) -> web.Response:
    settings: Settings = request.app["settings"]
    service: YooKassaService = request.app["yookassa_service"]
    if not service or not service.configured:
        return _json_error(400, "payment_unavailable", "Payment method unavailable")

    try:
        traffic_sale = _sale_mode_is_traffic(sale_mode)
        hwid_devices_sale = _sale_mode_is_hwid_devices(sale_mode)
        payment = await _create_base_payment_record(
            session,
            user_id=user_id,
            amount=price,
            currency="RUB",
            status="pending_yookassa",
            description=description,
            months=int(float(months)) if not traffic_sale else int(float(traffic_gb or months)),
            provider="yookassa",
            sale_mode=sale_mode,
            tariff_key=_sale_mode_tariff_key(sale_mode),
            purchased_gb=float(traffic_gb or months) if traffic_sale else None,
            purchased_hwid_devices=int(float(months)) if hwid_devices_sale else None,
        )
        metadata = {
            "user_id": str(user_id),
            "subscription_months": str(
                int(float(months)) if not traffic_sale and not hwid_devices_sale else 0
            ),
            "payment_db_id": str(payment.payment_id),
            "sale_mode": sale_mode,
            "source": "webapp",
        }
        if traffic_sale:
            metadata["traffic_gb"] = _format_number_for_payload(traffic_gb or months)
        if hwid_devices_sale:
            metadata["hwid_devices"] = str(int(float(months)))
        if _sale_mode_tariff_key(sale_mode):
            metadata["tariff_key"] = _sale_mode_tariff_key(sale_mode)
        response = await service.create_payment(
            amount=price,
            currency="RUB",
            description=description,
            metadata=metadata,
            receipt_email=settings.YOOKASSA_DEFAULT_RECEIPT_EMAIL,
            save_payment_method=bool(
                settings.yookassa_autopayments_active
                and settings.YOOKASSA_AUTOPAYMENTS_REQUIRE_CARD_BINDING
            ),
        )
        payment_url = response.get("confirmation_url") if response else None
        if not payment_url:
            await payment_dal.update_payment_status_by_db_id(
                session, payment.payment_id, "failed_creation"
            )
            await session.commit()
            return _json_error(502, "payment_failed", "Failed to create payment")

        await payment_dal.update_payment_status_by_db_id(
            session,
            payment.payment_id,
            response.get("status", "pending"),
            yk_payment_id=response.get("id"),
        )
        await session.commit()
        return web.json_response(
            {
                "ok": True,
                "action": "open_link",
                "payment_url": payment_url,
                "payment_id": payment.payment_id,
            }
        )
    except Exception:
        await session.rollback()
        logger.exception("YooKassa WebApp payment failed")
        return _json_error(502, "payment_failed", "Failed to create payment")


async def _create_freekassa_payment(
    request: web.Request,
    session: AsyncSession,
    user_id: int,
    months: Any,
    price: float,
    description: str,
    *,
    sale_mode: str = "subscription",
    traffic_gb: Optional[float] = None,
) -> web.Response:
    request.app["settings"]
    service: FreeKassaService = request.app["freekassa_service"]
    if not service or not service.configured or not service.payment_method_id:
        return _json_error(400, "payment_unavailable", "Payment method unavailable")

    try:
        traffic_sale = _sale_mode_is_traffic(sale_mode)
        hwid_devices_sale = _sale_mode_is_hwid_devices(sale_mode)
        payment = await _create_base_payment_record(
            session,
            user_id=user_id,
            amount=price,
            currency=service.default_currency,
            status="pending_freekassa",
            description=description,
            months=int(float(months)) if not traffic_sale else int(float(traffic_gb or months)),
            provider="freekassa",
            sale_mode=sale_mode,
            tariff_key=_sale_mode_tariff_key(sale_mode),
            purchased_gb=float(traffic_gb or months) if traffic_sale else None,
            purchased_hwid_devices=int(float(months)) if hwid_devices_sale else None,
        )
        success, response_data = await service.create_order(
            payment_db_id=payment.payment_id,
            user_id=user_id,
            months=months,
            amount=price,
            currency=service.default_currency,
            payment_method_id=service.payment_method_id,
            ip_address=service.server_ip,
            extra_params={"us_method": service.payment_method_id},
        )
        payment_url = response_data.get("location") if success else None
        provider_id = response_data.get("orderHash") or response_data.get("orderId")
        if provider_id:
            await payment_dal.update_provider_payment_and_status(
                session, payment.payment_id, str(provider_id), payment.status
            )
            await session.commit()
        if not payment_url:
            await payment_dal.update_payment_status_by_db_id(
                session, payment.payment_id, "failed_creation"
            )
            await session.commit()
            return _json_error(502, "payment_failed", "Failed to create payment")
        return web.json_response(
            {
                "ok": True,
                "action": "open_link",
                "payment_url": payment_url,
                "payment_id": payment.payment_id,
            }
        )
    except Exception:
        await session.rollback()
        logger.exception("FreeKassa WebApp payment failed")
        return _json_error(502, "payment_failed", "Failed to create payment")


async def _create_platega_payment(
    request: web.Request,
    session: AsyncSession,
    user_id: int,
    months: Any,
    price: float,
    description: str,
    variant: str = "platega_sbp",
    sale_mode: str = "subscription",
    traffic_gb: Optional[float] = None,
) -> web.Response:
    settings: Settings = request.app["settings"]
    service: PlategaService = request.app["platega_service"]
    if not service or not service.configured:
        return _json_error(400, "payment_unavailable", "Payment method unavailable")
    if variant == "platega_crypto":
        if not settings.PLATEGA_CRYPTO_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        platega_method_id = settings.PLATEGA_CRYPTO_METHOD
    else:
        if variant == "platega_sbp" and not settings.PLATEGA_SBP_ENABLED:
            return _json_error(400, "payment_unavailable", "Payment method unavailable")
        platega_method_id = settings.platega_sbp_method_resolved

    try:
        traffic_sale = _sale_mode_is_traffic(sale_mode)
        hwid_devices_sale = _sale_mode_is_hwid_devices(sale_mode)
        payment = await _create_base_payment_record(
            session,
            user_id=user_id,
            amount=price,
            currency=settings.DEFAULT_CURRENCY_SYMBOL or "RUB",
            status="pending_platega",
            description=description,
            months=int(float(months)) if not traffic_sale else int(float(traffic_gb or months)),
            provider="platega",
            sale_mode=sale_mode,
            tariff_key=_sale_mode_tariff_key(sale_mode),
            purchased_gb=float(traffic_gb or months) if traffic_sale else None,
            purchased_hwid_devices=int(float(months)) if hwid_devices_sale else None,
        )
        months_for_provider = (
            int(float(months)) if not traffic_sale else int(float(traffic_gb or months))
        )
        payload = json.dumps(
            {
                "payment_db_id": payment.payment_id,
                "user_id": user_id,
                "months": months_for_provider if not traffic_sale else 0,
                "sale_mode": sale_mode,
                "traffic_gb": _format_number_for_payload(traffic_gb or months)
                if traffic_sale
                else None,
                "hwid_devices": int(float(months)) if hwid_devices_sale else None,
                "source": "webapp",
                "platega_variant": "crypto" if variant == "platega_crypto" else "sbp",
            }
        )
        success, response_data = await service.create_transaction(
            payment_db_id=payment.payment_id,
            user_id=user_id,
            months=months_for_provider,
            amount=price,
            currency=settings.DEFAULT_CURRENCY_SYMBOL or "RUB",
            description=description,
            payload=payload,
            payment_method=platega_method_id,
        )
        payment_url = (
            (
                response_data.get("redirect")
                or response_data.get("url")
                or response_data.get("paymentUrl")
            )
            if success
            else None
        )
        provider_id = response_data.get("transactionId") or response_data.get("id")
        if provider_id:
            await payment_dal.update_provider_payment_and_status(
                session,
                payment.payment_id,
                str(provider_id),
                str(response_data.get("status", payment.status)),
            )
            await session.commit()
        if not payment_url:
            await payment_dal.update_payment_status_by_db_id(
                session, payment.payment_id, "failed_creation"
            )
            await session.commit()
            return _json_error(502, "payment_failed", "Failed to create payment")
        return web.json_response(
            {
                "ok": True,
                "action": "open_link",
                "payment_url": payment_url,
                "payment_id": payment.payment_id,
            }
        )
    except Exception:
        await session.rollback()
        logger.exception("Platega WebApp payment failed")
        return _json_error(502, "payment_failed", "Failed to create payment")


async def _create_severpay_payment(
    request: web.Request,
    session: AsyncSession,
    user_id: int,
    months: Any,
    price: float,
    description: str,
    *,
    sale_mode: str = "subscription",
    traffic_gb: Optional[float] = None,
) -> web.Response:
    settings: Settings = request.app["settings"]
    service: SeverPayService = request.app["severpay_service"]
    if not service or not service.configured:
        return _json_error(400, "payment_unavailable", "Payment method unavailable")

    try:
        traffic_sale = _sale_mode_is_traffic(sale_mode)
        hwid_devices_sale = _sale_mode_is_hwid_devices(sale_mode)
        payment = await _create_base_payment_record(
            session,
            user_id=user_id,
            amount=price,
            currency=settings.DEFAULT_CURRENCY_SYMBOL or "RUB",
            status="pending_severpay",
            description=description,
            months=int(float(months)) if not traffic_sale else int(float(traffic_gb or months)),
            provider="severpay",
            sale_mode=sale_mode,
            tariff_key=_sale_mode_tariff_key(sale_mode),
            purchased_gb=float(traffic_gb or months) if traffic_sale else None,
            purchased_hwid_devices=int(float(months)) if hwid_devices_sale else None,
        )
        success, response_data = await service.create_payment(
            payment_db_id=payment.payment_id,
            user_id=user_id,
            months=months,
            amount=price,
            currency=settings.DEFAULT_CURRENCY_SYMBOL or "RUB",
            description=description,
        )
        payment_url = (
            (
                response_data.get("url")
                or response_data.get("payment_url")
                or response_data.get("paymentUrl")
            )
            if success
            else None
        )
        provider_id = response_data.get("id") or response_data.get("uid")
        if provider_id:
            await payment_dal.update_provider_payment_and_status(
                session, payment.payment_id, str(provider_id), payment.status
            )
            await session.commit()
        if not payment_url:
            await payment_dal.update_payment_status_by_db_id(
                session, payment.payment_id, "failed_creation"
            )
            await session.commit()
            return _json_error(502, "payment_failed", "Failed to create payment")
        return web.json_response(
            {
                "ok": True,
                "action": "open_link",
                "payment_url": payment_url,
                "payment_id": payment.payment_id,
            }
        )
    except Exception:
        await session.rollback()
        logger.exception("SeverPay WebApp payment failed")
        return _json_error(502, "payment_failed", "Failed to create payment")


async def _create_stars_payment(
    request: web.Request,
    session: AsyncSession,
    user_id: int,
    months: Any,
    stars_price: int,
    description: str,
    sale_mode: str = "subscription",
    traffic_gb: Optional[float] = None,
) -> web.Response:
    bot: Bot = request.app["bot"]
    try:
        traffic_sale = _sale_mode_is_traffic(sale_mode)
        hwid_devices_sale = _sale_mode_is_hwid_devices(sale_mode)
        payment = await _create_base_payment_record(
            session,
            user_id=user_id,
            amount=float(stars_price),
            currency="XTR",
            status="pending_stars",
            description=description,
            months=int(float(months)) if not traffic_sale else int(float(traffic_gb or months)),
            provider="telegram_stars",
            sale_mode=sale_mode,
            tariff_key=_sale_mode_tariff_key(sale_mode),
            purchased_gb=float(traffic_gb or months) if traffic_sale else None,
            purchased_hwid_devices=int(float(months)) if hwid_devices_sale else None,
        )
        payload_units = traffic_gb if traffic_sale and traffic_gb is not None else months
        payload = f"{payment.payment_id}:{_format_number_for_payload(payload_units)}:{sale_mode}"
        prices = [LabeledPrice(label=description, amount=stars_price)]
        create_invoice_link = getattr(bot, "create_invoice_link", None)
        if callable(create_invoice_link):
            invoice_url = await create_invoice_link(
                title=description,
                description=description,
                payload=payload,
                # Required to be empty for Telegram Stars (XTR) per Telegram Bot API.
                provider_token="",
                currency="XTR",
                prices=prices,
            )
            return web.json_response(
                {
                    "ok": True,
                    "action": "open_invoice",
                    "payment_url": invoice_url,
                    "payment_id": payment.payment_id,
                }
            )

        await bot.send_invoice(
            chat_id=user_id,
            title=description,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
        )
        return web.json_response(
            {
                "ok": True,
                "action": "invoice_sent",
                "payment_id": payment.payment_id,
            }
        )
    except Exception:
        await session.rollback()
        logger.exception("Stars WebApp payment failed")
        return _json_error(502, "payment_failed", "Failed to create invoice")
