from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable

import discord
import requests

from core.openhands_runtime import OpenHandsFlowError
from core.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_DISCORD_MESSAGE_LIMIT = 2000
_STREAM_CHUNK_SIZE = 220
_STREAM_EDIT_INTERVAL_SECONDS = 0.35


def send_discord_webhook(webhook_url: str, content: str) -> None:
    with tracer.start_as_current_span("discord.send_webhook") as span:
        span.set_attribute("discord.message_chars", len(content))
        logger.info("Sending Discord webhook notification chars=%s", len(content))
        response = requests.post(webhook_url, json={"content": content}, timeout=30)
        response.raise_for_status()
        span.set_attribute("http.status_code", response.status_code)
        logger.info("Sent Discord webhook notification status_code=%s", response.status_code)


class _DiscordGatewayClient(discord.Client):
    """Small Discord client that only needs to establish a bot session."""

    def __init__(
        self,
        ready_event: threading.Event,
        command_handler: Callable[[discord.Message], str | None],
        channel_id: int | None,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._ready_event = ready_event
        self._command_handler = command_handler
        self._channel_id = channel_id

    async def on_ready(self) -> None:
        logger.info("Discord bot connected user=%s", self.user)
        self._ready_event.set()

    async def on_message(self, message: discord.Message) -> None:
        if self.user is None:
            return
        if message.author.bot:
            return
        if not _is_target_channel(message, self._channel_id):
            return
        if self._channel_id is not None and self.user not in message.mentions:
            logger.debug(
                "Handling channel message without mention for dedicated triage channel"
            )

        with tracer.start_as_current_span("discord.on_message") as span:
            span.set_attribute("discord.message_id", message.id)
            span.set_attribute("discord.channel_id", message.channel.id)
            logger.info("Received Discord mention message_id=%s author=%s", message.id, message.author)
            placeholder = await message.reply("Thinking...", mention_author=False)
            try:
                async with message.channel.typing():
                    reply = await asyncio.to_thread(self._command_handler, message)
            except OpenHandsFlowError as exc:
                span.record_exception(exc)
                logger.warning(
                    "OpenHands flow failed for Discord message_id=%s detail=%s",
                    message.id,
                    exc.detail,
                )
                await placeholder.edit(content=exc.user_message[:_DISCORD_MESSAGE_LIMIT])
                return
            except Exception as exc:  # noqa: BLE001
                span.record_exception(exc)
                logger.exception("Failed to handle Discord mention message_id=%s: %s", message.id, exc)
                await placeholder.edit(content="I hit an internal error while processing that request.")
                return

            if not reply:
                await placeholder.edit(content="I could not produce a reply.")
                return

            span.set_attribute("discord.reply_chars", len(reply))
            logger.info("Streaming Discord reply message_id=%s chars=%s", message.id, len(reply))
            await _stream_message_edit(placeholder, reply)


async def _stream_message_edit(message: discord.Message, content: str) -> None:
    """Simulate streaming by progressively editing one Discord message."""

    with tracer.start_as_current_span("discord.stream_message_edit") as span:
        final_content = content[:_DISCORD_MESSAGE_LIMIT]
        span.set_attribute("discord.final_chars", len(final_content))
        if len(final_content) <= _STREAM_CHUNK_SIZE:
            await message.edit(content=final_content)
            return

        rendered = ""
        for chunk_start in range(0, len(final_content), _STREAM_CHUNK_SIZE):
            chunk = final_content[chunk_start : chunk_start + _STREAM_CHUNK_SIZE]
            rendered = f"{rendered}{chunk}"
            await message.edit(content=rendered)
            if len(rendered) < len(final_content):
                await asyncio.sleep(_STREAM_EDIT_INTERVAL_SECONDS)


class DiscordNotifier:
    """Deliver messages via Discord bot when available, otherwise fall back to webhook."""

    def __init__(
        self,
        *,
        webhook_url: str | None,
        bot_token: str | None,
        channel_id: int | None,
        status_provider: Callable[[], str] | None = None,
        conversation_provider: Callable[[str, str], str] | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._bot_token = bot_token
        self._channel_id = channel_id
        self._status_provider = status_provider
        self._conversation_provider = conversation_provider
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
        self._client = _DiscordGatewayClient(
            self._ready_event,
            self._handle_command,
            self._channel_id,
        )

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

    def _handle_command(self, message: discord.Message) -> str | None:
        """Route every operator mention through the conversational LLM path."""

        if self._client is None or self._client.user is None:
            return "I am still starting up."

        content = message.content
        mention_tokens = (self._client.user.mention, f"<@!{self._client.user.id}>", f"<@{self._client.user.id}>")
        normalized = content
        for token in mention_tokens:
            normalized = normalized.replace(token, "")
        normalized = normalized.strip()
        if self._conversation_provider is not None:
            prompt = normalized or "Please introduce yourself, explain what you monitor, and summarize your current status."
            conversation_key = _conversation_key_for_message(message)
            logger.info(
                "Dispatching conversational prompt chars=%s conversation_key=%s",
                len(prompt),
                conversation_key,
            )
            return self._conversation_provider(conversation_key, prompt)
        return "Conversational replies are not configured yet."


def _conversation_key_for_message(message: discord.Message) -> str:
    """Build a stable per-thread/per-channel conversation key for Discord chat state."""

    if message.guild is None:
        scope = "dm"
        scope_id = str(message.channel.id)
    else:
        scope = "guild"
        scope_id = str(message.guild.id)
    thread_id = _discord_thread_id(message.channel)
    if thread_id is not None:
        channel_id = str(thread_id)
    else:
        channel_id = str(message.channel.id)
    return f"{scope}-{scope_id}-channel-{channel_id}"


def _discord_thread_id(channel: discord.abc.Messageable) -> int | None:
    """Return thread id when message is posted inside a thread."""

    thread_id = getattr(channel, "id", None)
    if thread_id is None:
        return None
    if isinstance(channel, discord.Thread):
        return thread_id
    if isinstance(channel, discord.abc.Messageable):
        parent_id = getattr(channel, "parent_id", None)
        if parent_id is None:
            return None
        return thread_id
    return None


def _is_target_channel(message: discord.Message, configured_channel_id: int | None) -> bool:
    """Whether the message is in the configured channel or one of its threads."""

    if configured_channel_id is None:
        return True

    if message.guild is None:
        return False

    if message.channel.id == configured_channel_id:
        return True

    parent_id = getattr(message.channel, "parent_id", None)
    if parent_id is None:
        return False
    return int(parent_id) == configured_channel_id
