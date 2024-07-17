import logging
import os
from logging.config import dictConfig

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "management_file": {
            "level": "INFO",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": "management.log",
            "mode": "w",
        },
        "transactions_file": {
            "level": "WARNING",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": "transactions.log",
            "mode": "w",
        },
        "error_file": {
            "level": "ERROR",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": "error.log",
            "mode": "w",
        },
    },
    "loggers": {
        "": {
            "handlers": ["management_file", "transactions_file", "error_file"],
            "level": "DEBUG",
        },
    },
}


def setup_logging():
    dictConfig(LOGGING_CONFIG)
