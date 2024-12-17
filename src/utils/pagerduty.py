import logging

from config import PAGERDUTY, PAGERDUTY_INACTIVE
from utils import fetch

API_ALERT = 'https://events.pagerduty.com/v2/enqueue'


logger = logging.getLogger(__name__)

async def sendAlert(event, key=None, isResolve=False):
    summary = f'ALERT: {event}'
    if not isResolve:
        logger.warning(summary)

    dedup_key = key if key else event
    if PAGERDUTY_INACTIVE != '1':
        body = {
            "routing_key": PAGERDUTY,
            "event_action": "trigger" if not isResolve else 'resolve',
            "dedup_key": dedup_key,
            "payload": {
                "summary": event,
                "source": event,
                "severity": 'warning',
            }
        }
        return await fetch.post(API_ALERT, body)
