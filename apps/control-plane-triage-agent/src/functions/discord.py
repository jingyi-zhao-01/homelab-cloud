from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


def send_discord(webhook_url: str, content: str) -> None:
    logger.info("Sending Discord notification chars=%s", len(content))
    response = requests.post(webhook_url, json={"content": content}, timeout=30)
    response.raise_for_status()
    logger.info("Sent Discord notification status_code=%s", response.status_code)
