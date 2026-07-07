"""Migration engine: schema introspection helpers and the chain runner.

Chain definitions live in the sibling ``chain_*`` modules; this module owns
the ``Migration`` contract, the ``schema_migrations`` tracking table and the
apply/skip/namespace semantics.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

CORE_MIGRATION_NAMESPACE = "core"


@dataclass(frozen=True)
class Migration:
    id: str
    description: str
    upgrade: Callable[[Connection], None]


def _ensure_migrations_table(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )


def validate_migration_chains(chains: dict[str, list[Migration]]) -> None:
    """Reject malformed chains before anything touches the database.

    Non-core namespaces must prefix every migration id with ``"<namespace>."``
    so ids from different sources can never collide inside the shared
    ``schema_migrations`` table.
    """
    for namespace, migrations in chains.items():
        if namespace == CORE_MIGRATION_NAMESPACE:
            continue
        prefix = f"{namespace}."
        for migration in migrations:
            if not migration.id.startswith(prefix):
                raise ValueError(
                    f"Migration id {migration.id!r} in namespace {namespace!r} must "
                    f"start with {prefix!r}"
                )


def run_migration_chains(connection: Connection, chains: dict[str, list[Migration]]) -> None:
    """
    Apply pending migrations of every chain sequentially. Already applied
    revisions are skipped; all chains share the ``schema_migrations`` table.
    """
    validate_migration_chains(chains)
    _ensure_migrations_table(connection)

    applied_revisions: set[str] = {
        row[0] for row in connection.execute(text("SELECT id FROM schema_migrations"))
    }

    for namespace, migrations in chains.items():
        for migration in migrations:
            if migration.id in applied_revisions:
                continue

            logger.info(
                "Migrator: applying %s – %s (namespace %s)",
                migration.id,
                migration.description,
                namespace,
            )
            try:
                with connection.begin_nested():
                    migration.upgrade(connection)
                    connection.execute(
                        text("INSERT INTO schema_migrations (id) VALUES (:revision)"),
                        {"revision": migration.id},
                    )
            except Exception as exc:
                logger.exception(
                    "Migrator: failed to apply %s (%s)", migration.id, migration.description
                )
                raise exc
            else:
                logger.info("Migrator: migration %s applied successfully", migration.id)
