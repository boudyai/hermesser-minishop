"""HermesProvisioningService — replaces PanelApiService for hermes hosting.

Single swap point: build_services.py constructs this instead of PanelApiService.
Translates the panel-API method surface into provisioning-core REST calls.

Payment-path methods call provisioning-core (POST /tenants, activate/suspend).
Proxy-specific methods (squads, hwid, bandwidth, happ) return empty no-ops —
they have no Hermes equivalent and are never on the payment path.

See initial-docs/minishop-integration-map.md §1/§3 for the full method map.
"""

from __future__ import annotations

import json
import logging
import time
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


def _localize_core_error(settings: Any, status_code: int, body: str) -> Dict[str, Any]:
    """Translate a provisioning-core error response via the minishop i18n catalog.

    The provisioning-core API returns ``{"detail": {"error_code": ..., "params": ...}}``
    on HTTPException. We look up the ``error_code`` in the same locale catalog the
    bot uses, fall back to the English ``message`` field the core shipped, and
    fall back further to ``body[:500]`` when the body isn't parseable JSON.
    """
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "status_code": status_code, "message": body[:500]}
    detail = data.get("detail") if isinstance(data, dict) else None
    if not isinstance(detail, dict):
        return {"error": True, "status_code": status_code, "message": body[:500]}
    error_code = detail.get("error_code")
    if not error_code:
        message = detail.get("message") if isinstance(detail, str) else body[:500]
        return {"error": True, "status_code": status_code, "message": message}
    from bot.middlewares.i18n import get_i18n_instance

    i18n = get_i18n_instance()
    lang = getattr(settings, "DEFAULT_LANGUAGE", "en") or "en"
    raw_params = detail.get("params")
    params: Dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
    message = i18n.gettext(lang, str(error_code), **params)
    return {
        "error": True,
        "status_code": status_code,
        "message": message,
        "error_code": error_code,
    }


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
        # Tenant-state cache: 5s TTL is short enough that the UI reflects
        # in-flight provisioning jobs within a few seconds, while keeping
        # the per-page-load cost at one core hit per tenant.
        self._tenant_state_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._tenant_state_ttl_seconds: float = 5.0

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
        bot_username: Optional[str] = None,
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

        # ponytail: pass bot_username through so the core populates
        # tenants.bot_username at create time. The minishop side already
        # resolved it via Telegram getMe at the entry point; without
        # this, the field stays NULL and the UI can't show the bot's
        # @handle on the Home card. owner_telegram_id is the customer's
        # numeric Telegram user ID — provisioner uses it to scope the
        # hosted Hermes bot to the owner (TELEGRAM_ALLOWED_USERS) and
        # to make the customer's DM the platform home channel.
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "bot_token": bot_token,
            "owner_telegram_id": int(telegram_id),
        }
        if bot_username:
            payload["bot_username"] = str(bot_username).lstrip("@").strip() or None

        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/shop/tenants",
            json=payload,
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

                # ponytail: minishop's _get_or_create_panel_user_link_details
                # requires a non-empty subscriptionUuid/shortUuid on the
                # returned panel user, otherwise the trial rolls back with
                # `trial_activation_failed_panel_link` (502) and retries loop
                # forever. Hermes has no proxy subscription link, so we
                # synthesize one from the tenant id; both are opaque UUIDs
                # from minishop's perspective.
                return {
                    "response": {
                        "uuid": tenant_id,
                        "username": username_on_panel,
                        "subscriptionUuid": tenant_id,
                        "shortUuid": tenant_id[:8],
                    }
                }
            body = await resp.text()
            log.error("provisioning-core POST /shop/tenants failed: %s %s", resp.status, body[:200])
            return _localize_core_error(self.settings, resp.status, body)

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
                    # ponytail: surface bot_username so the Mini App's
                    # "Открыть бота" button gets the @handle even when the
                    # cached active-subscription payload is stale.
                    "botUsername": data.get("bot_username") or "",
                }
            if resp.status == 404:
                return None
            log.error("GET /shop/tenants/%s failed: %s", user_uuid, resp.status)
            return None

    async def get_user_by_uuid_lookup(
        self, user_uuid: str, log_response: bool = False
    ) -> Dict[str, Any]:
        # ponytail: the base class hits /users/{uuid} which requires mTLS; here
        # we have only the shop API key, so route to /shop/tenants/{uuid}
        # instead. The result shape mirrors PanelApiUsersMixin.
        session = await self._core_get_session()
        async with session.get(f"{self._core_base_url}/shop/tenants/{user_uuid}") as resp:
            if resp.status == 200:
                data = await resp.json()
                return {
                    "ok": True,
                    "user": {
                        "uuid": str(data.get("tenant_id", user_uuid)),
                        "status": str(data.get("status", "unknown") or "unknown"),
                        # ponytail: lifecycle_details.py reads expireAt at
                        # lines 75/86/109/120 to compute
                        # is_active_based_on_panel; without this the code
                        # hits UnboundLocalError on panel_expire_dt and
                        # /api/me returns 500. The shop API doesn't track
                        # subscription expiry (the minishop does), so we
                        # pass through the tenant's last_state_change as
                        # a best-effort substitute.
                        "expireAt": str(data.get("last_state_change", "") or ""),
                        # ponytail: bot_username drives the "Открыть бота"
                        # button in the Mini App. Without it the frontend
                        # disables the CTA even when the bot is healthy.
                        "botUsername": str(data.get("bot_username") or ""),
                    },
                    "not_found": False,
                    "failure_reason": None,
                }
            if resp.status == 404:
                return {
                    "ok": False,
                    "user": None,
                    "not_found": True,
                    "failure_reason": "classification=panel_lookup_not_found",
                }
            log.error("GET /shop/tenants/%s failed: %s", user_uuid, resp.status)
            return {
                "ok": False,
                "user": None,
                "not_found": False,
                "failure_reason": f"classification=panel_lookup_failed status={resp.status}",
            }

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

    # ============================================
    # Subscription page config (proxy-era, not in hermes)
    # ============================================

    async def get_subscription_page_config_list(self) -> Optional[Dict[str, Any]]:
        # ponytail: the proxy-era Remnawave panel has no hermes equivalent.
        # Returning None here matches the "panel unreachable" contract so
        # the webapp falls back to its built-in guide instead of logging
        # a 401 from the core.
        return None

    async def get_subscription_page_config_by_short_uuid(
        self, short_uuid: str
    ) -> Optional[Dict[str, Any]]:
        return None

    async def get_subscription_page_config_by_uuid(
        self, config_uuid: str
    ) -> Optional[Dict[str, Any]]:
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

    async def update_tenant_bot_token(
        self,
        tenant_id: str,
        bot_token: str,
        bot_username: Optional[str] = None,
        owner_telegram_id: Optional[int] = None,
    ) -> bool:
        """Apply a freshly-saved bot token to a running tenant.

        Returns True on 202; False on 4xx/5xx. The bot token was already
        validated against Telegram getMe at the entry point (Mini App or
        bot FSM) so we don't repeat that check here. The core enqueues
        an update_secrets job that the worker drains — by the time the
        user reloads the status screen, the container is rewriting
        secrets.env and restarting with the new token.
        """
        payload: Dict[str, Any] = {"bot_token": bot_token}
        if bot_username:
            # ponytail: the core updates tenants.bot_username alongside
            # the encrypted token so the Home card shows the @handle.
            payload["bot_username"] = str(bot_username).lstrip("@").strip() or None
        if owner_telegram_id is not None:
            # ponytail: include the owner's numeric Telegram user ID so
            # the provisioner can refresh TELEGRAM_ALLOWED_USERS +
            # home_channel on this update_secrets job. Without this
            # the existing allow-list survives but the new owner
            # (e.g. bot transferred) would still be blocked.
            payload["owner_telegram_id"] = int(owner_telegram_id)
        session = await self._core_get_session()
        try:
            async with session.put(
                f"{self._core_base_url}/shop/tenants/{tenant_id}/bot_token",
                json=payload,
            ) as resp:
                if resp.status == 202:
                    log.info("Bot token update queued for tenant %s", tenant_id)
                    return True
                body = await resp.text()
                log.error(
                    "PUT /shop/tenants/%s/bot_token failed: %s %s",
                    tenant_id,
                    resp.status,
                    body[:200],
                )
                return False
        except aiohttp.ClientError as exc:
            log.error("Bot token update network error for %s: %s", tenant_id, exc)
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

    async def topup_tenant_quota(
        self, tenant_id: str, amount_usd: float
    ) -> Optional[Dict[str, Any]]:
        """Bump the tenant's active LiteLLM key max_budget by `amount_usd`.

        Called from the CornLLM topup success path. The core
        enqueues an `update_litellm_key` job that the worker drains
        from dacha. Returns the response body (delta_usd,
        new_max_budget_usd) on success, None on 5xx.
        """
        session = await self._core_get_session()
        async with session.post(
            f"{self._core_base_url}/shop/tenants/{tenant_id}/quota/topup",
            json={"amount_usd": float(amount_usd)},
        ) as resp:
            if resp.status in (200, 202):
                return await resp.json()
            body = await resp.text()
            log.error(
                "Quota topup failed for %s: %s %s",
                tenant_id,
                resp.status,
                body[:200],
            )
            return None

    async def get_tenant_cornllm_key(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the tenant's CornLLM virtual key for the user-facing
        Settings UI. Returns None on 404 (no active key) or 5xx; the
        caller renders the appropriate copy.
        """
        session = await self._core_get_session()
        async with session.get(
            f"{self._core_base_url}/shop/tenants/{tenant_id}/cornllm-key"
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            body = await resp.text()
            log.warning(
                "CornLLM key fetch failed for %s: %s %s",
                tenant_id,
                resp.status,
                body[:200],
            )
            return None

    async def get_tenant_state(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tenant runtime state from provisioning-core with short TTL cache.

        Returns None if the tenant doesn't exist (404) or the core is unreachable
        AND no cache is available. Returns a dict with: tenant_id, status,
        desired_state, actual_state, last_state_change (ISO 8601 string or None).
        Used by the webapp serializer to drive the in-progress / error /
        grace-period UI states on HomeScreen.
        """
        now = time.monotonic()
        cached = self._tenant_state_cache.get(tenant_id)
        if cached is not None and (now - cached[0]) < self._tenant_state_ttl_seconds:
            return cached[1]
        try:
            session = await self._core_get_session()
        except Exception as exc:  # noqa: BLE001 — best-effort cache
            log.warning("Tenant state fetch — session build failed for %s: %s", tenant_id, exc)
            return cached[1] if cached is not None else None
        try:
            async with session.get(f"{self._core_base_url}/shop/tenants/{tenant_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # ``resp.json()`` parses the FastAPI response into
                    # primitives, so ``last_state_change`` is already an
                    # ISO 8601 string (or None) — pass it through verbatim.
                    # Pydantic-side ``datetime`` conversion is the
                    # producer's job, not the consumer's.
                    last_change = data.get("last_state_change")
                    result: Dict[str, Any] = {
                        "tenant_id": str(data.get("tenant_id", tenant_id)),
                        "status": str(data.get("status", "unknown") or "unknown"),
                        "desired_state": str(data.get("desired_state", "unknown") or "unknown"),
                        "actual_state": str(data.get("actual_state", "unknown") or "unknown"),
                        "last_state_change": (str(last_change) if last_change else None),
                    }
                    self._tenant_state_cache[tenant_id] = (now, result)
                    return result
                if resp.status == 404:
                    # Don't cache 404 — tenant may be created imminently (trial).
                    return None
                log.error("GET /shop/tenants/%s failed: %s", tenant_id, resp.status)
                return cached[1] if cached is not None else None
        except aiohttp.ClientError as exc:
            log.warning("Tenant state fetch network error for %s: %s", tenant_id, exc)
            return cached[1] if cached is not None else None
        except Exception as exc:  # noqa: BLE001 — defensive
            log.warning("Tenant state fetch unexpected error for %s: %s", tenant_id, exc)
            return cached[1] if cached is not None else None

    def invalidate_tenant_state(self, tenant_id: str) -> None:
        """Drop the cached tenant state for a given id. Call after restart / suspend /
        activate / delete so the next page load reflects fresh state without waiting
        for TTL expiry."""
        self._tenant_state_cache.pop(tenant_id, None)
