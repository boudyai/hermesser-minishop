import asyncio
import logging
import sys

from dotenv import load_dotenv
from startup_banner import print_startup_banner

from app_logging import configure_logging
from bot.main_bot import run_bot
from config.settings import get_settings

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    await run_bot(settings)


if __name__ == "__main__":
    load_dotenv()
    print_startup_banner("backend")
    configure_logging()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Backend stopped")
    except Exception as exc:
        logger.critical("Backend failed: %s", exc, exc_info=True)
        sys.exit(1)
