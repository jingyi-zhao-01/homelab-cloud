from __future__ import annotations

import requests


def send_discord(webhook_url: str, content: str) -> None:
    response = requests.post(webhook_url, json={"content": content}, timeout=30)
    response.raise_for_status()
