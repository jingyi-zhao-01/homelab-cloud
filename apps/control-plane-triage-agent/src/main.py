from core.config import load_config
from core.tracing import configure_tracing
from functions.discord import DiscordNotifier
from run_time.service import TriageService
from util.logging_utils import configure_logging


def main() -> None:
    configure_logging()
    configure_tracing("control-plane-triage-agent")
    config = load_config()
    service = TriageService(config)
    notifier = DiscordNotifier(
        webhook_url=config.discord_webhook_url,
        bot_token=config.discord_bot_token,
        channel_id=config.discord_channel_id,
        status_provider=service.render_status,
        conversation_provider=service.answer_operator_prompt,
    )
    service.set_notifier(notifier)
    notifier.start()
    try:
        service.run_forever()
    finally:
        notifier.close()


if __name__ == "__main__":
    main()
