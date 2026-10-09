"""
Structured logging setup using structlog.
Compatible with Python 3.14+.
"""
from __future__ import annotations

import logging
import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for console output."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "hotel_concierge") -> structlog.BoundLogger:
    return structlog.get_logger(name)
