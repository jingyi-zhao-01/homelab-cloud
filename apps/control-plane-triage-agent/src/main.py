from core.config import load_config
from run_time.service import TriageService
from util.logging_utils import configure_logging


def main() -> None:
    configure_logging()
    config = load_config()
    TriageService(config).run_forever()


if __name__ == "__main__":
    main()
