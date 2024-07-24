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
        "management_info": {
            "level": "INFO",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "management_info.log"),
            "mode": "w",
        },
        "management_error": {
            "level": "ERROR",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "management_error.log"),
            "mode": "w",
        },
        "transactions_info": {
            "level": "INFO",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "transactions_info.log"),
            "mode": "w",
        },
        "transactions_error": {
            "level": "ERROR",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "transactions_error.log"),
            "mode": "w",
        },
        "investments_info": {
            "level": "ERROR",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "investments_info.log"),
            "mode": "w",
        },
        "investments_error": {
            "level": "ERROR",
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "investments_error.log"),
            "mode": "w",
        },
    },
    "loggers": {
        "management_info": {
            "handlers": ["management_info"],
            "level": "INFO",
            "propagate": False,
        },
        "management_error": {
            "handlers": ["management_error"],
            "level": "ERROR",
            "propagate": False,
        },
        "transactions_info": {
            "handlers": ["transactions_info"],
            "level": "INFO",
            "propagate": False,
        },
        "transactions_error": {
            "handlers": ["transactions_error"],
            "level": "ERROR",
            "propagate": False,
        },
        "investments_info": {
            "handlers": ["investments_info"],
            "level": "INFO",
            "propagate": False,
        },
        "investments_error": {
            "handlers": ["investments_error"],
            "level": "ERROR",
            "propagate": False,
        },
        "": {
            "handlers": [
                "management_info",
                "management_error",
                "transactions_info",
                "transactions_error",
                "investments_info",
                "investments_error",
            ],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}


def setup_logging():
    dictConfig(LOGGING_CONFIG)
