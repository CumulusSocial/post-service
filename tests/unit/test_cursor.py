from datetime import UTC, datetime
from uuid import uuid4

from post_service.services.posts import _decode_cursor, _encode_cursor


def test_cursor_roundtrip() -> None:
    ts = datetime(2026, 5, 9, 12, 34, 56, tzinfo=UTC)
    pid = uuid4()
    c = _encode_cursor(ts, pid)
    ts2, pid2 = _decode_cursor(c)
    assert ts2 == ts
    assert pid2 == pid
