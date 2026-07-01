"""HermesProvisioningService — replaces PanelApiService for hermes hosting.

Single swap point: build_services.py constructs this instead of PanelApiService.
Translates the panel-API method surface into provisioning-core REST calls.

Payment-path methods call provisioning-core (POST /tenants, activate/suspend).
Proxy-specific methods (squads, hwid, bandwidth, happ) return empty no-ops —
they have no Hermes equivalent and are never on the payment path.

See initial-docs/minishop-integration-map.md §1/§3 for the full method map.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_DNS, uuid5

import aiohttp

from backend.config.settings import Settings
from backend.bot.services.panel_api_service import PanelApiService

log = logging.getLogger(__name__)


class HermesProvisioningService(PanelApiService):
    """PanelApiService replacement that routes to hermes provisioning-core.

    Constructed in build_services.py when settings indicate hermes mode.
    The provisioning-core URL and key come from settings.panel_settings
    (reusing PANEL_API_URL / PANEL_API_KEY env vars for minimal config churn).
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._core_base_url = (self.base_url or "").rstrip("/")
        self._core_api_key = self.api_key or ""
        self._core_session: Optional[aiohttp.ClientSession] = None

    async def _core_get_session(self) -> aiohttp.ClientSession:
        if self._core_session is None or self._core_session.closed:
            headers = {"Content-Type": "application/json"}
            if self._core_api_key:
                headers["Authorization"] = f"Bearer {self._core_api_key}"
            self._core_session = aiohttp.ClientSession(headers=headers)
        return self._core_session

    async def close_session(self) -> None:
        if self._core_session and not self._core_session.closed:
            await self._core_session.close()
        await super().close_session()

    def _core_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._core_api_key:
            headers["Authorization"] = f"Bearer {self._core_api_key}"
        return headers

    @staticmethod
    def _user_id_from_telegram(telegram_id: int) -> str:
        return str(uuid5(NAMESPACE_DNS, f"tg-{telegram_id}"))

    # ============================================
    # Payment path: tenant lifecycle
    # ============================================

    async def create_panel_user(
        self,
        username_on_panel: str,
        telegram_id: Optional[int] = None,
        email: Optional[str] = None,
        default_expire_days: int = 1,
        default_traffic_limit_bytes: int = 0,
        default_traffic_limit_strategy: str = "NO_RESET",
        hwid_device_limit: Optional[int] = None,
        specific_squad_uuids: Optional[List[str]] = None,
        external_squad_uuid: Optional[str] = None,
        description: Optional[str] = None,
        tag: Optional[str] = None,
        status: str = "ACTIVE",
        log_response: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if telegram_id is None:
            log.error("create_panel_user requires telegram_id for hermes tenant creation")
            return {"error": True, "status_code": 400, "message": "telegram_id required"}

        user_id = self._user_id_from_telegram(telegram_id)
        # ponytail: bot_token placeholder — real token collected via Mini App
        # before this point. TODO: wire actual bot_token from user onboarding.
        bot_token = f"placeholder:{user_id}"

        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/tenants",
            json={"user_id": user_id, "bot_token": bot_token},
        ) as resp:
            if resp.status == 202:
                data = await resp.json()
                tenant_id = data.get("tenant_id", "")
                log.info("Hermes tenant created: %s (user_id=%s)", tenant_id, user_id)
                return {"response": {"uuid": tenant_id, "username": username_on_panel}}
            body = await resp.text()
            log.error("provisioning-core POST /tenants failed: %s %s", resp.status, body[:200])
            return {"error": True, "status_code": resp.status, "message": body[:500]}

    async def update_user_details_on_panel(
        self, user_uuid: str, update_payload: Dict[str, Any], log_response: bool = False
    ) -> Optional[Dict[str, Any]]:
        # Shop tracks expiry in its own Subscription.end_date. Provisioning-core
        # only cares about lifecycle transitions (create/suspend/delete), not
        # every expiry extension. This is a no-op success.
        log.debug("update_user_details_on_panel: no-op for hermes (uuid=%s)", user_uuid)
        return {"uuid": user_uuid, "status": "ACTIVE"}

    async def update_user_status_on_panel(
        self, user_uuid: str, enable: bool, log_response: bool = False
    ) -> bool:
        action = "activate" if enable else "suspend"
        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/tenants/{user_uuid}/{action}"
        ) as resp:
            if resp.status in (200, 202):
                log.info("Tenant %s %sd", user_uuid, action)
                return True
            body = await resp.text()
            log.error("Tenant %s %s failed: %s %s", user_uuid, action, resp.status, body[:200])
            return False

    async def delete_user_from_panel(
        self, user_uuid: str, log_response: bool = False
    ) -> Optional[Dict[str, Any]]:
        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/tenants/{user_uuid}/delete",
            json={"retain_backup_days": 30},
        ) as resp:
            if resp.status in (200, 202):
                log.info("Tenant %s deleted", user_uuid)
                return {"response": {"uuid": user_uuid, "deleted": True}}
            if resp.status == 404:
                log.info("Tenant %s already deleted", user_uuid)
                return {"response": {"uuid": user_uuid, "deleted": True}}
            body = await resp.text()
            log.error("Tenant %s delete failed: %s %s", user_uuid, resp.status, body[:200])
            return {"error": True, "status_code": resp.status, "message": body[:500]}

    async def get_user_by_uuid(
        self, user_uuid: str, log_response: bool = False
    ) -> Optional[Dict[str, Any]]:
        session = await self._core_get_session()
        async with session.get(f"{self._core_base_url}/tenants/{user_uuid}") as resp:
            if resp.status == 200:
                data = await resp.json()
                return {
                    "uuid": data.get("tenant_id", user_uuid),
                    "status": data.get("status", "unknown"),
                    "expireAt": data.get("last_state_change", ""),
                }
            if resp.status == 404:
                return None
            log.error("GET /tenants/%s failed: %s", user_uuid, resp.status)
            return None

    async def get_users_by_filter(
        self,
        telegram_id: Optional[int] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        log_response: bool = False,
    ) -> Optional[List[Dict[str, Any]]]:
        # No identity resolution via provisioning-core. The shop uses its own
        # DB (User.panel_user_uuid) for lookups. Return None → caller creates.
        return None

    async def get_all_panel_users(
        self, page_size: int, log_responses: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        return []

    # ============================================
    # Proxy-specific methods: no-ops
    # ============================================

    async def get_subscription_link(self, short_uuid: str) -> str:
        return ""

    async def get_user_devices(self, user_uuid: str) -> List[Dict[str, Any]]:
        return []

    async def disconnect_device(self, device_id: str) -> bool:
        return True

    async def get_internal_squads(self) -> List[Dict[str, Any]]:
        return []

    async def get_hosts(self) -> List[Dict[str, Any]]:
        return []

    async def encrypt_happ_link(self, raw_link: str) -> Optional[str]:
        return None

    async def reset_user_traffic(self, user_uuid: str) -> bool:
        return True

    async def get_system_stats(self) -> Optional[Dict[str, Any]]:
        return None

    async def get_bandwidth_stats(self) -> Optional[Dict[str, Any]]:
        return None

    async def get_user_bandwidth_stats(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        return None

    async def add_users_to_internal_squad(
        self, squad_uuid: str, user_uuids: List[str]
    ) -> bool:
        return True

    async def remove_users_from_internal_squad(
        self, squad_uuid: str, user_uuids: List[str]
    ) -> bool:
        return True
