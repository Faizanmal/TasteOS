"""Structured logging helpers that never emit secrets."""

from __future__ import annotations

import logging
import re

_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
_SENSITIVE = re.compile(
    r"(?i)(api[_-]?key|authorization|x-api-key|qloo_api_key|tasteos_api_key)"
    r"\s*[:=]\s*\S+"
)
# Soft PII / profile fields if they ever appear in free-form log strings.
_PROFILEISH = re.compile(r"(?i)\b(email|phone|password|ssn)\b\s*[:=]\s*\S+")


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def redact(text: str) -> str:
    # Bearer first so "Authorization: Bearer <token>" does not leave the token behind.
    cleaned = _BEARER.sub("Bearer [REDACTED]", text)
    cleaned = _SENSITIVE.sub(r"\1=[REDACTED]", cleaned)
    return _PROFILEISH.sub(r"\1=[REDACTED]", cleaned)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
