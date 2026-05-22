"""Structured JSON logging to stdout."""

import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    RESERVED_ATTRS = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self.RESERVED_ATTRS and not k.startswith("_"):
                out[k] = v
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
