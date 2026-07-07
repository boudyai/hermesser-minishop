"""Idempotent schema migrator: engine primitives + append-only chains."""

from typing import TYPE_CHECKING

from sqlalchemy.engine import Connection

from .chains import MIGRATIONS
from .engine import (
    CORE_MIGRATION_NAMESPACE,
    Migration,
    run_migration_chains,
    validate_migration_chains,
)

if TYPE_CHECKING:
    from config.settings import Settings

__all__ = [
    "CORE_MIGRATION_NAMESPACE",
    "MIGRATIONS",
    "Migration",
    "run_all_migration_chains",
    "run_database_migrations",
    "run_migration_chains",
    "validate_migration_chains",
]


def run_database_migrations(connection: Connection) -> None:
    """Apply the core migration chain (kept for restore/import code paths)."""
    run_migration_chains(connection, {CORE_MIGRATION_NAMESPACE: MIGRATIONS})


def run_all_migration_chains(connection: Connection, settings: "Settings") -> None:
    """Apply the core chain plus every plugin-contributed chain."""
    # Imported lazily: the plugin loader lives in the bot layer and must not
    # become an import-time dependency of the db layer.
    from bot.plugins import collect_migrations

    chains: dict[str, list[Migration]] = {CORE_MIGRATION_NAMESPACE: MIGRATIONS}
    chains.update(collect_migrations(settings))
    run_migration_chains(connection, chains)
