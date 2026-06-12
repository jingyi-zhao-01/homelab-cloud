from __future__ import annotations

import asyncio
import logging
import threading

import discord
import requests

logger = logging.getLogger(__name__)


def send_discord_webhook(webhook_url: str, content: str) -> None:
    logger.info("Sending Discord webhook notification chars=%s", len(content))
    response = requests.post(webhook_url, json={"content": content}, timeout=30)
    response.raise_for_status()
    logger.info("Sent Discord webhook notification status_code=%s", response.status_code)


class _DiscordGatewayClient(discord.Client):
    """Small Discord client that only needs to establish a bot session."""

    def __init__(self, ready_event: threading.Event) -> None:
        super().__init__(intents=discord.Intents.none())
        self._ready_event = ready_event

    async def on_ready(self) -> None:
        logger.info("Discord bot connected user=%s", self.user)
        self._ready_event.set()


class DiscordNotifier:
    """Deliver messages via Discord bot when available, otherwise fall back to webhook."""

    def __init__(
        self,
        *,
        webhook_url: str | None,
        bot_token: str | None,
        channel_id: int | None,
    ) -> None:
        self._webhook_url = webhook_url
        self._bot_token = bot_token
        self._channel_id = channel_id
        self._ready_event = threading.Event()
        self._startup_error: Exception | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: _DiscordGatewayClient | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the Discord gateway session so the bot shows online."""

        if not self._bot_token or self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run_gateway, name="discord-gateway", daemon=True)
        self._thread.start()
        if not self._ready_event.wait(timeout=30):
            raise RuntimeError("Timed out waiting for Discord bot to become ready")
        if self._startup_error is not None:
            raise RuntimeError("Failed to start Discord bot session") from self._startup_error

    def send(self, content: str) -> None:
        """Send one notification using bot delivery when configured."""

        if self._bot_token and self._channel_id is not None:
            if self._loop is None or self._client is None:
                raise RuntimeError("Discord bot notifier has not been started")
            future = asyncio.run_coroutine_threadsafe(self._send_bot_message(content), self._loop)
            future.result(timeout=30)
            return

        if not self._webhook_url:
            raise RuntimeError("No Discord delivery mechanism configured")
        send_discord_webhook(self._webhook_url, content)

    def close(self) -> None:
        """Shut down the Discord gateway session if one is running."""

        if self._loop is None or self._client is None:
            return
        future = asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
        future.result(timeout=30)

    def _run_gateway(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._client = _DiscordGatewayClient(self._ready_event)

        async def runner() -> None:
            try:
                assert self._client is not None
                await self._client.start(self._bot_token)
            except Exception as exc:  # noqa: BLE001
                self._startup_error = exc
                self._ready_event.set()
                logger.exception("Discord bot gateway exited with error: %s", exc)
                raise

        try:
            loop.run_until_complete(runner())
        finally:
            loop.close()

    async def _send_bot_message(self, content: str) -> None:
        assert self._client is not None
        assert self._channel_id is not None
        channel = self._client.get_channel(self._channel_id)
        if channel is None:
            channel = await self._client.fetch_channel(self._channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            raise RuntimeError(f"Configured Discord channel {self._channel_id} is not messageable")
        logger.info("Sending Discord bot notification channel_id=%s chars=%s", self._channel_id, len(content))
        await channel.send(content)
        logger.info("Sent Discord bot notification channel_id=%s", self._channel_id)
