"""
FinShield - Structured Logger (ELK-Compatible)
Outputs JSON logs for Logstash ingestion via stdout and TCP (port 5000).
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime, timezone


class ELKJsonFormatter(logging.Formatter):
    """Formats logs as JSON for ELK Stack ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "finshield-api",
            "environment": os.getenv("APP_ENV", "production"),
        }

        # Attach any extra fields passed via `extra={...}`
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno",
                "pathname", "filename", "module", "exc_info", "exc_text",
                "stack_info", "lineno", "funcName", "created", "msecs",
                "relativeCreated", "thread", "threadName", "processName",
                "process", "message", "taskName",
            ):
                log_entry[key] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_structured_logger(name: str) -> logging.Logger:
    """Returns a structured JSON logger. Streams to stdout always.
    If LOGSTASH_HOST is set, also streams JSON lines to Logstash over TCP."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        formatter = ELKJsonFormatter()

        # Always log to stdout (captured by Docker / journald)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

        # Optionally ship to Logstash via TCP (set LOGSTASH_HOST env var)
        logstash_host = os.getenv("LOGSTASH_HOST", "")
        logstash_port = int(os.getenv("LOGSTASH_PORT", "5000"))
        if logstash_host:
            try:
                tcp_handler = logging.handlers.SocketHandler(logstash_host, logstash_port)
                tcp_handler.setFormatter(formatter)
                logger.addHandler(tcp_handler)
            except Exception:
                pass  # Don't fail app startup if Logstash is unreachable

        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
