from __future__ import annotations

import logging
import sys


_LOG_FORMAT = '[%(asctime)s] %(levelname)s %(message)s'


def get_logger(name: str = 'psytest') -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


log = get_logger()