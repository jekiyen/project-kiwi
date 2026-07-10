import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_NAMED_LOGGERS = {
    "scanner": "scanner.log",
    "telegram": "telegram.log",
    "notifications": "notifications.log",
    "application": "application.log",
}


def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")

    def rotating_handler(filename: str) -> logging.Handler:
        h = logging.handlers.RotatingFileHandler(
            LOG_DIR / filename,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        h.setFormatter(formatter)
        return h

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    # errors.log captures ERROR+ from all loggers
    error_handler = rotating_handler("errors.log")
    error_handler.setLevel(logging.ERROR)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(error_handler)

    for name, filename in _NAMED_LOGGERS.items():
        log = logging.getLogger(name)
        log.setLevel(level)
        log.addHandler(rotating_handler(filename))
        log.propagate = True
