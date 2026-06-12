from core.config import load_config
from functions.discord import DiscordNotifier
from run_time.service import TriageService
from util.logging_utils import configure_logging


def main() -> None:
    configure_logging()
    config = load_config()
    notifier = DiscordNotifier(
        webhook_url=config.discord_webhook_url,
        bot_token=config.discord_bot_token,
        channel_id=config.discord_channel_id,
    )
    notifier.start()
    try:
        TriageService(config, notifier).run_forever()
    finally:
        notifier.close()


if __name__ == "__main__":
    main()
