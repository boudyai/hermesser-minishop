import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.services.panel_api_service import PanelApiService


class PanelApiServiceLoggingTests(unittest.IsolatedAsyncioTestCase):
    def _make_service(self) -> PanelApiService:
        return PanelApiService(
            SimpleNamespace(
                PANEL_API_URL="https://panel.example.test/api",
                PANEL_API_KEY="panel-key",
                USER_HWID_DEVICE_LIMIT=None,
            )
        )

    async def test_update_user_details_does_not_log_full_response_by_default(self):
        service = self._make_service()
        service._request = AsyncMock(return_value={"response": {"uuid": "user-uuid"}})

        with patch("bot.services.panel_api_service.logging.info") as info_log:
            result = await service.update_user_details_on_panel(
                "user-uuid",
                {"description": "profile"},
            )

        self.assertEqual(result, {"uuid": "user-uuid"})
        service._request.assert_awaited_once_with(
            "PATCH",
            "/users",
            json={"description": "profile", "uuid": "user-uuid"},
            log_full_response=False,
        )
        info_log.assert_not_called()

    async def test_update_user_details_can_still_request_full_response_logging(self):
        service = self._make_service()
        service._request = AsyncMock(return_value={"response": {"uuid": "user-uuid"}})

        await service.update_user_details_on_panel(
            "user-uuid",
            {"description": "profile"},
            log_response=True,
        )

        self.assertTrue(service._request.await_args.kwargs["log_full_response"])


if __name__ == "__main__":
    unittest.main()
