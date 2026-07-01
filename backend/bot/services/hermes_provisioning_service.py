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
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_DNS, uuid5

import aiohttp

try:
    from backend.bot.services.panel_api_service import PanelApiService
    from backend.config.settings import Settings
except ImportError:
    # ponytail: VPS container runs with pythonpath=backend, so bare imports work;
    # local venv uses pythonpath=. so the backend.* prefix is required. Both work.
    from bot.services.panel_api_service import PanelApiService  # type: ignore[no-redef]
    from config.settings import Settings  # type: ignore[no-redef]

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
        bot_token: Optional[str] = None,
        description: Optional[str] = None,
        tag: Optional[str] = None,
        status: str = "ACTIVE",
        log_response: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if telegram_id is None:
            log.error("create_panel_user requires telegram_id for hermes tenant creation")
            return {"error": True, "status_code": 400, "message": "telegram_id required"}

        user_id = self._user_id_from_telegram(telegram_id)
        if not bot_token:
            log.error("create_panel_user requires bot_token for hermes tenant creation")
            return {"error": True, "status_code": 400, "message": "bot_token required"}

        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/shop/tenants",
            json={"user_id": user_id, "bot_token": bot_token},
        ) as resp:
            if resp.status == 202:
                data = await resp.json()
                tenant_id = data.get("tenant_id", "")
                tenant_status = data.get("status", "")
                jobs_queued = data.get("jobs_queued", [])
                log.info(
                    "Hermes tenant: %s (user_id=%s, status=%s)", tenant_id, user_id, tenant_status
                )

                # Renewal reactivation: if the tenant already existed and is
                # suspended (expired subscription), re-activate it so the
                # container restarts and the LiteLLM key gets un-revoked.
                if tenant_status in ("suspended", "payment_expiring") and not jobs_queued:
                    log.info("Reactivating suspended tenant %s after renewal", tenant_id)
                    async with session.post(
                        f"{self._core_base_url}/shop/tenants/{tenant_id}/activate"
                    ) as activate_resp:
                        if activate_resp.status not in (200, 202):
                            act_body = await activate_resp.text()
                            log.error(
                                "Reactivation failed for %s: %s %s",
                                tenant_id,
                                activate_resp.status,
                                act_body[:200],
                            )

                return {"response": {"uuid": tenant_id, "username": username_on_panel}}
            body = await resp.text()
            log.error("provisioning-core POST /shop/tenants failed: %s %s", resp.status, body[:200])
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
        async with session.post(f"{self._core_base_url}/shop/tenants/{user_uuid}/{action}") as resp:
            if resp.status in (200, 202):
                log.info("Tenant %s %sd", user_uuid, action)
                return True
            body = await resp.text()
            log.error("Tenant %s %s failed: %s %s", user_uuid, action, resp.status, body[:200])
            return False

    async def delete_user_from_panel(self, user_uuid: str, log_response: bool = False) -> bool:
        del log_response
        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/shop/tenants/{user_uuid}/delete",
            json={"retain_backup_days": 30},
        ) as resp:
            if resp.status in (200, 202):
                log.info("Tenant %s deleted", user_uuid)
                return True
            if resp.status == 404:
                log.info("Tenant %s already deleted", user_uuid)
                return True
            body = await resp.text()
            log.error("Tenant %s delete failed: %s %s", user_uuid, resp.status, body[:200])
            return False

    async def get_user_by_uuid(
        self, user_uuid: str, log_response: bool = False
    ) -> Optional[Dict[str, Any]]:
        session = await self._core_get_session()
        async with session.get(f"{self._core_base_url}/shop/tenants/{user_uuid}") as resp:
            if resp.status == 200:
                data = await resp.json()
                return {
                    "uuid": data.get("tenant_id", user_uuid),
                    "status": data.get("status", "unknown"),
                    "expireAt": data.get("last_state_change", ""),
                }
            if resp.status == 404:
                return None
            log.error("GET /shop/tenants/%s failed: %s", user_uuid, resp.status)
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
        self,
        page_size: Optional[int] = None,
        log_responses: bool = False,
    ) -> Optional[List[Dict[str, Any]]]:
        return []

    # ============================================
    # Proxy-specific methods: no-ops
    # ============================================

    async def get_subscription_link(
        self,
        short_uuid_or_sub_uuid: str,
        client_type: Optional[str] = None,
    ) -> Optional[str]:
        return ""

    async def get_user_devices(self, user_uuid: str) -> List[Dict[str, Any]]:
        return []

    async def disconnect_device(self, user_uuid: str, hwid: str) -> bool:
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

    async def add_users_to_internal_squad(self, squad_uuid: str, user_uuids: List[str]) -> bool:
        return True

    async def remove_users_from_internal_squad(
        self, squad_uuid: str, user_uuids: List[str]
    ) -> bool:
        return True

    # ============================================
    # Env editor (shop API)
    # ============================================

    async def get_user_env(self, tenant_id: str) -> str:
        session = await self._core_get_session()
        async with session.get(f"{self._core_base_url}/shop/tenants/{tenant_id}/env") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("env_content", "")
            log.error("GET /shop/tenants/%s/env failed: %s", tenant_id, resp.status)
            return ""

    async def set_user_env(self, tenant_id: str, content: str) -> bool:
        session = await self._core_get_session()
        async with session.put(
            f"{self._core_base_url}/shop/tenants/{tenant_id}/env",
            json={"env_content": content},
        ) as resp:
            if resp.status == 200:
                log.info("Env updated for tenant %s", tenant_id)
                return True
            body = await resp.text()
            log.error("PUT /shop/tenants/%s/env failed: %s %s", tenant_id, resp.status, body[:200])
            return False

    # ============================================
    # Tenant management (restart, quota, logs)
    # ============================================

    async def restart_tenant(self, tenant_id: str) -> bool:
        session = await self._core_get_session()
        async with session.post(f"{self._core_base_url}/shop/tenants/{tenant_id}/restart") as resp:
            if resp.status == 202:
                log.info("Tenant %s restart queued", tenant_id)
                return True
            body = await resp.text()
            log.error("Restart failed for %s: %s %s", tenant_id, resp.status, body[:200])
            return False

    async def get_tenant_quota(self, tenant_id: str) -> Dict[str, Any] | None:
        session = await self._core_get_session()
        async with session.get(f"{self._core_base_url}/shop/tenants/{tenant_id}/quota") as resp:
            if resp.status == 200:
                return await resp.json()
            log.error("Quota fetch failed for %s: %s", tenant_id, resp.status)
            return None

    async def get_tenant_logs(self, tenant_id: str) -> str:
        session = await self._core_get_session()
        async with session.get(f"{self._core_base_url}/shop/tenants/{tenant_id}/logs") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("logs", "")
            return ""

    async def refresh_tenant_logs(self, tenant_id: str) -> bool:
        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/shop/tenants/{tenant_id}/logs/refresh"
        ) as resp:
            return resp.status == 202
