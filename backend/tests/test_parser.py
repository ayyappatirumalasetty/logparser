from datetime import datetime
import pytest
from app.parser import TimestampParser

@pytest.mark.parametrize(("line", "expected"), [
    ("2026/07/18 09:28:37:450 hi", datetime(2026,7,18,9,28,37,450000)),
    ("2026-01-23T13:08:26,879 hi", datetime(2026,1,23,13,8,26,879000)),
    ("2025-11-13 07:50:16,335 hi", datetime(2025,11,13,7,50,16,335000)),
    ("2026-02-16 07:40:11.981 hi", datetime(2026,2,16,7,40,11,981000)),
    ("18-Jul-2026 09:28:37 hi", datetime(2026,7,18,9,28,37)),
    ("Jul 18 09:28:37 host", datetime(2026,7,18,9,28,37)),
])
def test_supported_formats(line, expected):
    assert TimestampParser(2026).extract_timestamp(line) == expected
