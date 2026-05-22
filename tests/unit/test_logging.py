import json
import logging

from docbot.logging_setup import configure_logging


def test_log_emits_json(capsys):
    configure_logging(level=logging.INFO)
    log = logging.getLogger("docbot.test")
    log.info("hello", extra={"investigation_id": "abc"})
    captured = capsys.readouterr().out.strip()
    record = json.loads(captured)
    assert record["msg"] == "hello"
    assert record["investigation_id"] == "abc"
    assert record["level"] == "INFO"
