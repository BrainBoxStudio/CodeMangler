"""Logging filter that redacts known sensitive values from log records
(CLAUDE.md section 14: never log original secrets or print them to console).
"""
from __future__ import annotations

import logging


class RedactingFilter(logging.Filter):
    def __init__(self, sensitive_values: set[str] | None = None) -> None:
        super().__init__()
        self._sensitive_values: set[str] = sensitive_values or set()

    def track(self, value: str) -> None:
        if value:
            self._sensitive_values.add(value)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for value in self._sensitive_values:
            if value and value in message:
                message = message.replace(value, "[REDACTED]")
        record.msg = message
        record.args = ()
        return True


def configure_safe_logging(logger: logging.Logger) -> RedactingFilter:
    redacting_filter = RedactingFilter()
    logger.addFilter(redacting_filter)
    return redacting_filter
