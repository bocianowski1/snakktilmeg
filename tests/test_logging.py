import json
import logging

from lib.logging import JsonFormatter
from lib.utils import timed


def test_json_formatter_emits_core_fields_and_extra_fields() -> None:
    record = logging.LogRecord(
        name="snakktilmeg.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="transcript ready",
        args=(),
        exc_info=None,
    )
    record.event = "transcript_ready"
    record.transcript = "hello"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "snakktilmeg.test"
    assert payload["event"] == "transcript_ready"
    assert payload["transcript"] == "hello"
    assert "timestamp" in payload


def test_timed_logs_duration(caplog) -> None:
    @timed
    def sample() -> str:
        return "done"

    with caplog.at_level(logging.INFO):
        assert sample() == "done"

    assert caplog.records[0].event == "function_timed"
    assert caplog.records[0].function == "sample"
    assert caplog.records[0].duration_seconds >= 0
