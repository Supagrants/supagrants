import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_project_root() -> Path:
    return Path(__file__).parent.parent


logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ENVIRONMENT = os.getenv("ENVIRONMENT", "")

MONGO_SERVER = os.getenv("MONGO_SERVER", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_CONNECTION = os.getenv("MONGO_CONNECTION", None)
MONGO_DB = 'supagrants'

TELEGRAM_BOT = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_BOT_ID = os.getenv("TELEGRAM_BOT_ID", "")  # todo
TELEGRAN_BOT_HANDLE = os.getenv("TELEGRAN_BOT_HANDLE", "@supgrantsBot")

# PagerDuty & Support
PAGERDUTY_INACTIVE = os.getenv("PAGERDUTY_INACTIVE", 0)
PAGERDUTY = os.getenv("PAGERDUTY", "")