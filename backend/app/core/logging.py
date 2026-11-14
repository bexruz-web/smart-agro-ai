"""Strukturalangan JSON loglar. Token, kalit va telefon raqamlari loglarga yozilmaydi."""
import json
import logging
import re
import sys
from datetime import datetime, timezone

_SECRET_PATTERNS = [
    re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,}"),  # Telegram bot token
    re.compile(r"sk-ant-[A-Za-z0-9_-]+"),  # Anthropic kaliti
    re.compile(r"sa_[A-Za-z0-9_-]{20,}"),  # qurilma tokeni
    re.compile(r"\+?998\d{9}"),  # O'zbekiston telefon raqami
]


def scrub(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": scrub(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = scrub(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # httpx so'rov URL'larida bot tokeni bo'ladi — ularni INFO darajasida yozmaymiz
    logging.getLogger("httpx").setLevel(logging.WARNING)
