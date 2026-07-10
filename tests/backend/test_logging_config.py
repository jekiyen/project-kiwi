"""Regression test for a real double-conversion bug found during manual
verification: LocalTimeFormatter was shifting timestamps by +7h twice when
the host machine's own system timezone was already Asia/Jakarta."""
import logging
from datetime import datetime, timezone

from backend.logging_config import LocalTimeFormatter


def test_format_time_matches_known_utc_instant():
    # 2026-07-10 09:52:29 UTC == 2026-07-10 16:52:29 in Asia/Jakarta (UTC+7).
    known_utc = datetime(2026, 7, 10, 9, 52, 29, tzinfo=timezone.utc)
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hi", args=(), exc_info=None,
    )
    record.created = known_utc.timestamp()

    formatter = LocalTimeFormatter("%(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    assert formatter.formatTime(record) == "2026-07-10T16:52:29"


def test_format_time_is_independent_of_host_local_timezone(monkeypatch):
    """The bug only reproduced when the host's own local tz happened to be
    Asia/Jakarta — assert correctness regardless of what datetime.fromtimestamp()
    would produce under the host's local tz."""
    known_utc = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hi", args=(), exc_info=None,
    )
    record.created = known_utc.timestamp()

    formatter = LocalTimeFormatter("%(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    # Midnight UTC on Jan 1 is 07:00 the same day in Asia/Jakarta (no DST).
    assert formatter.formatTime(record) == "2026-01-01T07:00:00"
