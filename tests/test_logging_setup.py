import json
import logging

from cloudops_agent.logging_setup import configure_logging


def test_configure_logging_emits_single_line_json(capsys):
    configure_logging("debug")
    logger = logging.getLogger("cloudops_agent.test")
    try:
        raise ValueError("bad\nthing")
    except ValueError:
        logger.exception("failed %s", "op")
    lines = [line for line in capsys.readouterr().out.splitlines() if line]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["level"] == "ERROR"
    assert record["logger"] == "cloudops_agent.test"
    assert record["message"] == "failed op"
    assert "ValueError" in record["exc_info"]
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_is_idempotent(capsys):
    configure_logging("INFO")
    configure_logging("INFO")
    logging.getLogger("x").info("once")
    assert len([line for line in capsys.readouterr().out.splitlines() if line]) == 1
