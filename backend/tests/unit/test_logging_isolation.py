"""Test runs must not write to the production log file."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

import backend.common.logger  # noqa: F401  (configures the logger at import)


def test_tests_do_not_log_to_the_service_log_file():
    if os.environ.get("LOG_TO_FILE", "").lower() == "true":
        return  # explicitly opted in
    file_handlers = [h for name in ("app", "") for h in logging.getLogger(name).handlers if isinstance(h, RotatingFileHandler)]
    assert not file_handlers, f"tests are writing to {[h.baseFilename for h in file_handlers]}"
