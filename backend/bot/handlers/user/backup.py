"""Stream H: bot /backup and /restore commands.

Manual backup with a 3-hour cooldown (subscription.last_manual_backup_at);
manual restore is a two-step FSM — /restore asks for the zip, the next
document upload triggers the upload.

The actual zipping lives in provisioning-core; this module only enqueues
the job and uploads the bytes. The provisioner pushes the produced zip
to the owner via the tenant's own bot, and replies via provisioning-core
to the restore request when the job lands.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from io import BytesIO

from aiogram import Bot, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.subscription_service_impl.core import SubscriptionService
from config.settings import Settings

logger = logging.getLogger(__name__)

router = Router(name="user_backup_router")


class RestoreFSM(StatesGroup):
    waiting_for_backup_file = State()


BACKUP_COOLDOWN_HOURS = 0  # disabled
MAX_RESTORE_BYTES = 50 * 1024 * 1024


def _is_hermes(settings: Settings) -> bool:
    return str(getattr(settings.panel_settings, "write_mode", "") or "").lower() == "hermes"


def _i18n(i18n_data: dict | None):
    """Same lambda pattern tenant.py uses everywhere."""
    i18n = (i18n_data or {}).get("i18n_instance")
    current_lang = (i18n_data or {}).get("current_language", "ru")

    def _(key: str, default: str | None = None, **kw) -> str:
        if i18n is not None:
            try:
                text = i18n.gettext(current_lang, key, **kw)
                if text and text != key:
                    return text
            except Exception:
                pass
        if default is None:
            return key
        try:
            return str(default).format(**kw)
        except (KeyError, IndexError):
            return str(default)

    return _


async def _get_hermes_panel(subscription_service: SubscriptionService):
    # ponytail: same indirection tenant.py uses — keep the import lazy so
    # the legacy panel deployment doesn't drag Hermes into its import graph.
    from bot.services.hermes_provisioning_service import HermesProvisioningService

    panel_service = getattr(subscription_service, "panel_service", None)
    if not isinstance(panel_service, HermesProvisioningService):
        return None
    return panel_service


async def _get_active_subscription(
    session: AsyncSession, user_id: int
):
    """Return the user's active subscription or None.

    A user may have multiple historical rows; we pick the latest one
    marked ``is_active``. Same query shape tenant.py uses via
    ``subscription_service.get_active_subscription_details``, but here we
    need the model instance itself to read/write ``last_manual_backup_at``.
    """
    from db.models import Subscription

    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.is_active.is_(True))
        .order_by(Subscription.subscription_id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ============================================
# /backup — manual backup with cooldown
# ============================================


@router.message(Command("backup"))
async def backup_command(
    message: types.Message,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    i18n_data: dict | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    _ = _i18n(i18n_data)

    if not _is_hermes(settings):
        return

    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await message.answer(_("service_unavailable", default="Service unavailable."))
        return

    sub = await _get_active_subscription(session, user_id)
    if sub is None or not sub.panel_user_uuid:
        await message.answer(
            _(
                "tg_hermes_no_active_bot_short",
                default="No active bot.",
            )
        )
        return

    result = await panel_service.backup_tenant(str(sub.panel_user_uuid))
    if not result:
        await message.answer(
            _(
                "tg_hermes_backup_failed",
                default="❌ Could not start backup. Try again later.",
            )
        )
        return

    await message.answer(
        _(
            "tg_hermes_backup_queued",
            default=(
                "💾 Backup in progress. "
                "You'll receive the file from your bot shortly."
            ),
        )
    )


# ============================================
# /restore — FSM asking for the zip
# ============================================


@router.message(Command("restore"))
async def restore_command(
    message: types.Message,
    state: FSMContext,
    settings: Settings,
    i18n_data: dict | None = None,
) -> None:
    _ = _i18n(i18n_data)
    if not _is_hermes(settings):
        return
    await state.set_state(RestoreFSM.waiting_for_backup_file)
    await message.answer(
        _(
            "tg_hermes_restore_prompt",
            default=(
                "📥 Send the backup .zip file. "
                "⚠️ Current data will be overwritten."
            ),
        )
    )


@router.message(StateFilter(RestoreFSM.waiting_for_backup_file), F.document)
async def receive_backup_file(
    message: types.Message,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
    subscription_service: SubscriptionService,
    session: AsyncSession,
    i18n_data: dict | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    _ = _i18n(i18n_data)

    if not _is_hermes(settings):
        await state.clear()
        return

    document = message.document
    if document is None:
        await state.clear()
        return

    filename = document.file_name or "restore.zip"
    if not filename.lower().endswith(".zip"):
        await message.answer(
            _(
                "tg_hermes_restore_wrong_ext",
                default="❌ Only .zip files are accepted.",
            )
        )
        return

    size = int(document.file_size or 0)
    if size <= 0 or size > MAX_RESTORE_BYTES:
        await message.answer(
            _(
                "tg_hermes_restore_too_big",
                default="❌ File too large. Limit is 50 MB.",
            )
        )
        return

    panel_service = await _get_hermes_panel(subscription_service)
    if panel_service is None:
        await state.clear()
        await message.answer(_("service_unavailable", default="Service unavailable."))
        return

    sub = await _get_active_subscription(session, user_id)
    if sub is None or not sub.panel_user_uuid:
        await state.clear()
        await message.answer(
            _(
                "tg_hermes_no_active_bot_short",
                default="No active bot.",
            )
        )
        return

    # ponytail: download BEFORE clearing state so a download failure
    # leaves the user in the FSM and they can resend without retyping
    # /restore. Only clear on success or hard reject (wrong type/size).
    try:
        file = await bot.download(document)
        if file is None:
            raise RuntimeError("bot.download returned None")
        buffer = BytesIO()
        while True:
            chunk = file.read(64 * 1024)
            if not chunk:
                break
            buffer.write(chunk)
        zip_data = buffer.getvalue()
    except Exception:
        logger.exception("restore_download_failed user_id=%s", user_id)
        await message.answer(
            _(
                "tg_hermes_restore_download_failed",
                default="❌ Failed to download the file. Try again.",
            )
        )
        return

    await state.clear()

    if not zip_data:
        await message.answer(
            _(
                "tg_hermes_restore_empty",
                default="❌ Empty file.",
            )
        )
        return

    result = await panel_service.restore_tenant(
        str(sub.panel_user_uuid), zip_data, filename=filename
    )
    if not result:
        await message.answer(
            _(
                "tg_hermes_restore_failed",
                default="❌ Could not start restore. Try again later.",
            )
        )
        return

    await message.answer(
        _(
            "tg_hermes_restore_queued",
            default=(
                "♻️ Restore in progress. "
                "Your bot will reload when the data is in place."
            ),
        )
    )


# ============================================
# Cancel FSM via /start or any text while waiting
# ============================================


@router.message(StateFilter(RestoreFSM.waiting_for_backup_file), F.text)
async def restore_cancel_on_text(
    message: types.Message,
    state: FSMContext,
) -> None:
    # Any non-document text message while waiting → user gave up; let
    # other handlers (status, menu) take over and clear the FSM state.
    await state.clear()