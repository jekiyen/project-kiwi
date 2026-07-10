import contextvars
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path

from backend.core.timezone import to_local

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_NAMED_LOGGERS = {
    "scanner": "scanner.log",
    "telegram": "telegram.log",
    "notifications": "notifications.log",
    "application": "application.log",
}

# Set by the request-ID middleware for the duration of a request; read here so
# every log line emitted while handling that request can be tied back to it.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class LocalTimeFormatter(logging.Formatter):
    """Renders %(asctime)s in Asia/Jakarta regardless of host system timezone."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        # record.created is always a UTC epoch timestamp — anchor it explicitly
        # rather than going through the host's local timezone interpretation,
        # so this is correct no matter what timezone the server itself runs in.
        dt = to_local(datetime.fromtimestamp(record.created, tz=timezone.utc))
        return dt.strftime(datefmt or "%Y-%m-%dT%H:%M:%S")


def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"
    formatter = LocalTimeFormatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")
    request_id_filter = RequestIDFilter()

    def rotating_handler(filename: str) -> logging.Handler:
        h = logging.handlers.RotatingFileHandler(
            LOG_DIR / filename,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        h.setFormatter(formatter)
        h.addFilter(request_id_filter)
        return h

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(request_id_filter)

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
