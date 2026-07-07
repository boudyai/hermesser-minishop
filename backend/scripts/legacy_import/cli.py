"""CLI argument parsing and the import entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import Settings
from db.migrator import run_database_migrations
from db.models import Base

from .common import (
    SOURCE,
    _json_dumps,
    normalize_async_postgres_dsn,
)
from .remnashop import RemnashopImporter
from .remnashop_env import (
    read_remnashop_env_file,
)

logger = logging.getLogger(__name__)


def parse_only(value: str) -> set[str]:
    if not value:
        return set()
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def parse_tariff_map(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    path = Path(value)
    raw = path.read_text(encoding="utf-8") if path.exists() else value
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError("--tariff-map-json must be a JSON object or a path to one")
    return {str(key): str(mapped) for key, mapped in decoded.items()}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import legacy bot data into this shop.")
    parser.add_argument("--source-type", choices=[SOURCE], default=SOURCE)
    parser.add_argument("--source-dsn", required=True)
    parser.add_argument("--source-schema", default="public")
    parser.add_argument(
        "--source-env-file",
        help=(
            "Path to the source Remnashop .env. Used for APP_CRYPT_KEY, Remnawave "
            "API settings and selected safe compatibility values."
        ),
    )
    parser.add_argument(
        "--source-crypt-key",
        help="Explicit Remnashop APP_CRYPT_KEY. Overrides the value from --source-env-file.",
    )
    parser.add_argument("--target-dsn")
    parser.add_argument(
        "--only",
        default="all",
        help=(
            "Comma-separated sections: "
            "all,users,referrals,subscriptions,payments,promocodes,settings"
        ),
    )
    parser.add_argument(
        "--on-conflict",
        choices=["merge", "skip", "overwrite"],
        default="merge",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--created-by-admin-id", type=int, default=0)
    parser.add_argument(
        "--tariff-map-json",
        help="JSON object or path mapping remnashop plan id/name/tag to local tariff_key.",
    )
    parser.add_argument(
        "--no-admin-compat-overrides",
        action="store_true",
        help="Do not enable migration compatibility toggles in admin settings.",
    )
    return parser


async def _prepare_target_schema(engine: Any) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(run_database_migrations)


async def run_import(args: argparse.Namespace) -> dict[str, Any]:
    settings = Settings()
    source_env = read_remnashop_env_file(args.source_env_file)
    source_crypt_key = args.source_crypt_key or source_env.get("APP_CRYPT_KEY")
    source_engine = create_async_engine(normalize_async_postgres_dsn(args.source_dsn))
    target_engine = create_async_engine(
        normalize_async_postgres_dsn(args.target_dsn or settings.DATABASE_URL)
    )
    await _prepare_target_schema(target_engine)

    session_factory = async_sessionmaker(
        bind=target_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with source_engine.connect() as source, session_factory() as target:
        importer = RemnashopImporter(
            source=source,
            target=target,
            source_schema=args.source_schema,
            only=parse_only(args.only),
            on_conflict=args.on_conflict,
            dry_run=bool(args.dry_run),
            created_by_admin_id=args.created_by_admin_id,
            tariff_map=parse_tariff_map(args.tariff_map_json),
            write_admin_compat_overrides=not args.no_admin_compat_overrides,
            source_env=source_env,
            source_crypt_key=source_crypt_key,
            target_webhook_base_url=settings.WEBHOOK_BASE_URL,
            tariffs_config_path=settings.TARIFFS_CONFIG_PATH,
        )
        summary = await importer.run()
        if args.dry_run:
            await target.rollback()
        else:
            await target.commit()

    await source_engine.dispose()
    await target_engine.dispose()
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args()
    summary = asyncio.run(run_import(args))
    print(_json_dumps(summary))
