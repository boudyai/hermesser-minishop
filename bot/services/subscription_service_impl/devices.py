# ruff: noqa: F401,F403,F405,I001
from ._runtime import *  # noqa: F403,F405


class HwidDeviceMixin:
    async def activate_hwid_device_topup(
        self,
        session: AsyncSession,
        user_id: int,
        device_count: int,
        payment_amount: float,
        payment_db_id: int,
        provider: str = "yookassa",
        tariff_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            purchased_devices = int(device_count)
        except (TypeError, ValueError):
            purchased_devices = 0
        if purchased_devices <= 0:
            logging.error("HWID device top-up requires positive device count for user %s", user_id)
            return None

        db_user = await user_dal.get_user_by_id(session, user_id)
        if not db_user or not db_user.panel_user_uuid:
            return None
        sub = await subscription_dal.get_active_subscription_by_user_id(
            session, user_id, db_user.panel_user_uuid
        )
        if not sub:
            return None

        tariff = None
        if self._tariffs_config():
            tariff = self._resolve_tariff(tariff_key or sub.tariff_key)
            packages = (
                [*tariff.hwid_device_packages.rub, *tariff.hwid_device_packages.stars]
                if tariff.hwid_device_packages
                else []
            )
            if packages and not any(pkg.count == purchased_devices for pkg in packages):
                logging.error(
                    "HWID device package %s is not available for tariff %s",
                    purchased_devices,
                    tariff.key,
                )
                return None

        base_hwid_limit = (
            int(sub.hwid_device_limit)
            if sub.hwid_device_limit is not None
            else self._base_hwid_limit_for_tariff(tariff)
        )
        if base_hwid_limit == 0:
            logging.info(
                "Skipping HWID top-up for user %s because current limit is unlimited", user_id
            )
            return {
                "subscription_id": sub.subscription_id,
                "hwid_device_limit": 0,
                "extra_hwid_devices": int(sub.extra_hwid_devices or 0),
                "purchased_hwid_devices": 0,
            }

        new_extra_devices = int(sub.extra_hwid_devices or 0) + purchased_devices
        effective_hwid_limit = self._effective_hwid_limit(base_hwid_limit, new_extra_devices)
        await self._record_payment_context(
            session,
            payment_db_id,
            sale_mode="hwid_devices",
            tariff_key=tariff.key if tariff else sub.tariff_key,
            purchased_hwid_devices=purchased_devices,
        )
        updated_sub = await subscription_dal.update_subscription(
            session,
            sub.subscription_id,
            {
                "hwid_device_limit": base_hwid_limit,
                "extra_hwid_devices": new_extra_devices,
                "tariff_key": tariff.key if tariff else sub.tariff_key,
            },
        )
        if not updated_sub:
            return None

        panel_payload = self._build_panel_update_payload(
            panel_user_uuid=db_user.panel_user_uuid,
            expire_at=updated_sub.end_date,
            status="ACTIVE",
            hwid_device_limit=effective_hwid_limit,
        )
        panel_payload.update(self._panel_identity_payload_for_user(db_user))
        updated_panel = await self.panel_service.update_user_details_on_panel(
            db_user.panel_user_uuid,
            panel_payload,
        )
        if not updated_panel or updated_panel.get("error"):
            logging.warning(
                "Panel user HWID limit update failed for user %s. Response: %s",
                user_id,
                updated_panel,
            )
            return None

        await tariff_dal.create_hwid_device_purchase(
            session,
            subscription_id=updated_sub.subscription_id,
            payment_id=payment_db_id,
            purchased_devices=purchased_devices,
        )
        return {
            "subscription_id": updated_sub.subscription_id,
            "hwid_device_limit": effective_hwid_limit,
            "extra_hwid_devices": new_extra_devices,
            "purchased_hwid_devices": purchased_devices,
            "tariff_key": tariff.key if tariff else sub.tariff_key,
        }
