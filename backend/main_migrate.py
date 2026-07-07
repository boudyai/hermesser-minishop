import asyncio
import logging
import sys

from dotenv import load_dotenv
from startup_banner import print_startup_banner

from app_logging import configure_logging
from config.settings import get_settings
from db.database_setup import init_db, init_db_connection

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    session_factory = init_db_connection(settings)
    await init_db(settings, session_factory)


if __name__ == "__main__":
    load_dotenv()
    print_startup_banner("migrate")
    configure_logging()
    try:
        asyncio.run(main())
    except Exception as exc:
        logger.critical("Migration failed: %s", exc, exc_info=True)
        sys.exit(1)
