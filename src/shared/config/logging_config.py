import logging
import logging.config
import os
from typing import Optional

LOG_LEVEL = os.getenv("TRADING_LOG_LEVEL", "INFO").upper()

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": LOG_LEVEL,
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "logs/trading.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "level": LOG_LEVEL,
        },
    },
    "loggers": {
        "": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": True},
        "trading_executor": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "grpc_client": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}


def setup_logging(log_level: Optional[str] = None) -> None:
    if log_level:
        LOGGING_CONFIG["handlers"]["console"]["level"] = log_level
        LOGGING_CONFIG["handlers"]["file"]["level"] = log_level
        for logger in LOGGING_CONFIG["loggers"].values():
            logger["level"] = log_level

    os.makedirs("logs", exist_ok=True)
    logging.config.dictConfig(LOGGING_CONFIG)
