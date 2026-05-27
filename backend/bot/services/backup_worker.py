import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from aiogram import Bot
from aiogram.types import FSInputFile

from bot.infra.redis import redis_lock
from bot.services.backup_archive import (
    BACKUP_APP_ID,
    BACKUP_FILENAME_PREFIX,
    BACKUP_FORMAT_VERSION,
    attach_archive_integrity,
    build_file_records,
    write_manifest,
    write_zip_from_directory,
)
from config.settings import Settings

COMPOSE_MARKER_FILES = {
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
}
DEFAULT_COMPOSE_EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "backups",
    "node_modules",
    "postgres-data",
    "redis-data",
    "shop-data",
}
BACKUP_RUNTIME_SETTING_KEYS = {
    "BACKUP_ENABLED",
    "BACKUP_CHAT_ID",
    "BACKUP_THREAD_ID",
    "BACKUP_INTERVAL_SECONDS",
    "BACKUP_LOCAL_RETENTION",
    "BACKUP_POSTGRES_DUMP_ENABLED",
    "BACKUP_PG_DUMP_PATH",
    "BACKUP_PG_DUMP_TIMEOUT_SECONDS",
    "BACKUP_COMPOSE_ENABLED",
    "BACKUP_COMPOSE_SOURCE_DIR",
    "BACKUP_COMPOSE_EXCLUDE_DIRS",
}


@dataclass
class BackupResult:
    archive_path: Path
    started_at: datetime
    completed_at: datetime
    db_dump_included: bool
    compose_files_count: int
    size_bytes: int
    warnings: list[str] = field(default_factory=list)


class BackupWorker:
    SETTINGS_REFRESH_SECONDS = 60

    def __init__(self, settings: Settings, bot: Bot, session_factory=None):
        self.settings = settings
        self.bot = bot
        self.session_factory = session_factory

    async def run(self) -> None:
        while True:
            await self._refresh_settings()
            if not self.settings.BACKUP_ENABLED:
                await asyncio.sleep(self.SETTINGS_REFRESH_SECONDS)
                continue

            interval = self._interval_seconds()
            delay_seconds = self._seconds_until_next_slot(interval)
            if delay_seconds > 0:
                should_run = await self._sleep_until_next_slot(delay_seconds, interval)
                if not should_run:
                    continue

            await self._refresh_settings()
            if not self.settings.BACKUP_ENABLED:
                continue

            try:
                ttl_seconds = max(
                    60,
                    int(getattr(self.settings, "BACKUP_LOCK_TTL_SECONDS", 7200) or 7200),
                )
                async with redis_lock(
                    self.settings,
                    "backup-worker",
                    ttl_seconds=ttl_seconds,
                ) as acquired:
                    if acquired:
                        started = time.monotonic()
                        result = await self.create_and_send_backup()
                        logging.info(
                            "metric worker_tick_duration_seconds=%.3f worker=backup size_bytes=%s",
                            time.monotonic() - started,
                            result.size_bytes,
                        )
                    else:
                        logging.info(
                            "Backup worker tick skipped because another worker holds the lock"
                        )
            except Exception as exc:
                logging.exception("Backup worker tick failed")
                await self._notify_failure(exc)

    async def create_and_send_backup(self) -> BackupResult:
        result = await self.create_backup()
        try:
            await self.send_backup(result)
        finally:
            self.prune_old_backups()
        return result

    async def create_backup(self) -> BackupResult:
        started_at = datetime.now(timezone.utc)
        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S%z")
        archive_name = f"{BACKUP_FILENAME_PREFIX}{stamp}.zip"
        backup_dir = Path(self.settings.BACKUP_DIR).expanduser()
        backup_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix=f"{BACKUP_FILENAME_PREFIX}{stamp}-",
            dir=backup_dir,
        ) as tmp:
            staging_dir = Path(tmp)
            warnings: list[str] = []
            db_dump_included = False
            compose_files_count = 0

            if self.settings.BACKUP_POSTGRES_DUMP_ENABLED:
                dump_dir = staging_dir / "database"
                dump_dir.mkdir(parents=True, exist_ok=True)
                dump_path = dump_dir / f"{self.settings.POSTGRES_DB}.dump"
                await self._dump_database(dump_path)
                db_dump_included = True

            if self.settings.BACKUP_COMPOSE_ENABLED:
                compose_files_count = self._stage_compose_source(staging_dir / "compose", warnings)

            completed_at = datetime.now(timezone.utc)
            manifest = {
                "app": BACKUP_APP_ID,
                "format_version": BACKUP_FORMAT_VERSION,
                "type": "scheduled",
                "created_at": completed_at.isoformat(),
                "created_at_local": completed_at.astimezone().isoformat(),
                "postgres": {
                    "host": self.settings.POSTGRES_HOST,
                    "port": self.settings.POSTGRES_PORT,
                    "database": self.settings.POSTGRES_DB,
                    "user": self.settings.POSTGRES_USER,
                    "dump_format": "pg_dump custom",
                    "included": db_dump_included,
                },
                "compose": {
                    "source_dir": self.settings.BACKUP_COMPOSE_SOURCE_DIR,
                    "included": compose_files_count > 0,
                    "files_count": compose_files_count,
                },
                "warnings": warnings,
            }
            attach_archive_integrity(
                manifest,
                file_records=build_file_records(staging_dir),
            )
            write_manifest(staging_dir, manifest)

            tmp_archive = backup_dir / f"{archive_name}.tmp"
            archive_path = backup_dir / archive_name
            write_zip_from_directory(staging_dir, tmp_archive)
            tmp_archive.replace(archive_path)

        return BackupResult(
            archive_path=archive_path,
            started_at=started_at,
            completed_at=completed_at,
            db_dump_included=db_dump_included,
            compose_files_count=compose_files_count,
            size_bytes=archive_path.stat().st_size,
            warnings=warnings,
        )

    async def _dump_database(self, dump_path: Path) -> None:
        await asyncio.to_thread(self._run_pg_dump, dump_path)

    def _run_pg_dump(self, dump_path: Path) -> None:
        pg_dump_path = str(self.settings.BACKUP_PG_DUMP_PATH or "pg_dump")
        if shutil.which(pg_dump_path) is None and Path(pg_dump_path).name == pg_dump_path:
            raise RuntimeError(
                "pg_dump executable was not found. Rebuild the worker image with "
                "PostgreSQL client tools."
            )

        env = os.environ.copy()
        env["PGPASSWORD"] = self.settings.POSTGRES_PASSWORD
        command = [
            pg_dump_path,
            "-h",
            self.settings.POSTGRES_HOST,
            "-p",
            str(self.settings.POSTGRES_PORT),
            "-U",
            self.settings.POSTGRES_USER,
            "-d",
            self.settings.POSTGRES_DB,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(dump_path),
        ]
        timeout = max(30, int(self.settings.BACKUP_PG_DUMP_TIMEOUT_SECONDS or 1800))
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env=env,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"pg_dump failed with exit code {result.returncode}: {stderr[:500]}")

    def _stage_compose_source(self, target_dir: Path, warnings: list[str]) -> int:
        source_raw = (self.settings.BACKUP_COMPOSE_SOURCE_DIR or "").strip()
        if not source_raw:
            warnings.append("Compose source directory is not configured.")
            return 0

        source_dir = Path(source_raw).expanduser()
        if not source_dir.exists() or not source_dir.is_dir():
            warnings.append(f"Compose source directory is unavailable: {source_dir}")
            return 0

        if not any((source_dir / marker).is_file() for marker in COMPOSE_MARKER_FILES):
            warnings.append(f"Compose source directory has no compose file marker: {source_dir}")

        excluded_dirs = self._compose_excluded_dirs()
        files_count = 0
        target_dir.mkdir(parents=True, exist_ok=True)

        for path in source_dir.rglob("*"):
            relative = path.relative_to(source_dir)
            if any(part in excluded_dirs for part in relative.parts):
                continue
            if path.is_dir() or path.is_symlink():
                continue
            if path.name.startswith(f"{BACKUP_FILENAME_PREFIX}") and path.suffix == ".zip":
                continue
            destination = target_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(path, destination)
                files_count += 1
            except OSError as exc:
                warnings.append(f"Skipped compose file {relative.as_posix()}: {exc}")

        return files_count

    def _compose_excluded_dirs(self) -> set[str]:
        configured = self._split_csv(self.settings.BACKUP_COMPOSE_EXCLUDE_DIRS)
        return DEFAULT_COMPOSE_EXCLUDED_DIRS | set(configured)

    @staticmethod
    def _split_csv(value: Optional[str]) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    async def send_backup(self, result: BackupResult) -> None:
        chat_id = self._target_chat_id()
        if chat_id is None:
            logging.warning(
                "Backup archive created at %s but BACKUP_CHAT_ID/LOG_CHAT_ID is not configured",
                result.archive_path,
            )
            return

        kwargs = {
            "chat_id": chat_id,
            "document": FSInputFile(result.archive_path),
            "caption": self._caption(result),
        }
        thread_id = self._target_thread_id()
        if thread_id is not None:
            kwargs["message_thread_id"] = thread_id
        await self.bot.send_document(**kwargs)

    def prune_old_backups(self) -> None:
        retention = int(getattr(self.settings, "BACKUP_LOCAL_RETENTION", 3) or 0)
        if retention <= 0:
            return

        backup_dir = Path(self.settings.BACKUP_DIR).expanduser()
        archives = sorted(
            backup_dir.glob(f"{BACKUP_FILENAME_PREFIX}*.zip"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for archive in archives[retention:]:
            try:
                archive.unlink()
            except OSError:
                logging.exception("Failed to delete old backup archive %s", archive)

    def _target_chat_id(self) -> Optional[int]:
        return self.settings.BACKUP_CHAT_ID or self.settings.LOG_CHAT_ID

    def _target_thread_id(self) -> Optional[int]:
        return self.settings.BACKUP_THREAD_ID or self.settings.LOG_THREAD_ID

    def _caption(self, result: BackupResult) -> str:
        completed_at = result.completed_at.astimezone()
        lines = [
            "Remnawave Minishop backup",
            f"Created: {completed_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"Database dump: {'yes' if result.db_dump_included else 'no'}",
            f"Compose files: {result.compose_files_count}",
            f"Archive size: {self._human_size(result.size_bytes)}",
        ]
        if result.warnings:
            lines.append(f"Warnings: {len(result.warnings)}")
        return "\n".join(lines)

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        units: Iterable[str] = ("B", "KB", "MB", "GB")
        size = float(size_bytes)
        unit = "B"
        for unit in units:
            if size < 1024 or unit == "GB":
                break
            size /= 1024
        if unit == "B":
            return f"{int(size)} {unit}"
        return f"{size:.1f} {unit}"

    async def _refresh_settings(self) -> None:
        if self.session_factory is None:
            return
        try:
            from bot.services.settings_override_service import refresh_overrides_from_db

            await refresh_overrides_from_db(
                self.settings,
                self.session_factory,
                keys=BACKUP_RUNTIME_SETTING_KEYS,
            )
        except Exception:
            logging.exception("Failed to refresh backup settings from DB")

    def _interval_seconds(self) -> int:
        try:
            interval = int(self.settings.BACKUP_INTERVAL_SECONDS or 0)
        except (TypeError, ValueError):
            interval = 0
        return max(60, interval)

    def _seconds_until_next_slot(self, interval_seconds: int) -> float:
        now = datetime.now().astimezone()
        if interval_seconds <= 0:
            return 0.0
        if interval_seconds <= 24 * 60 * 60:
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elapsed = (now - midnight).total_seconds()
            remainder = elapsed % interval_seconds
        else:
            remainder = time.time() % interval_seconds
        if remainder < 0.5:
            return 0.0
        return max(0.0, interval_seconds - remainder)

    async def _sleep_until_next_slot(self, delay_seconds: float, interval_seconds: int) -> bool:
        deadline = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        while True:
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                return True
            await asyncio.sleep(min(remaining, self.SETTINGS_REFRESH_SECONDS))
            await self._refresh_settings()
            if not self.settings.BACKUP_ENABLED:
                return False
            if self._interval_seconds() != interval_seconds:
                return False

    async def _notify_failure(self, exc: Exception) -> None:
        chat_id = self._target_chat_id()
        if chat_id is None:
            return
        kwargs = {
            "chat_id": chat_id,
            "text": f"Remnawave Minishop backup failed: {type(exc).__name__}. Check worker logs.",
        }
        thread_id = self._target_thread_id()
        if thread_id is not None:
            kwargs["message_thread_id"] = thread_id
        try:
            await self.bot.send_message(**kwargs)
        except Exception:
            logging.exception("Failed to send backup failure notification")
