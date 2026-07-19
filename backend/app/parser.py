from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import LogEvent


class TimestampFormat(ABC):
    name: str
    pattern: re.Pattern[str]

    @abstractmethod
    def parse(self, raw: str, year: int) -> datetime: ...

    def extract(self, line: str, year: int) -> datetime | None:
        match = self.pattern.search(line)
        return self.parse(match.group(0), year) if match else None


class StrptimeFormat(TimestampFormat):
    def __init__(self, name: str, pattern: str, format_string: str, transform=None) -> None:
        self.name, self.pattern, self.format_string = name, re.compile(pattern), format_string
        self.transform = transform or (lambda value: value)

    def parse(self, raw: str, year: int) -> datetime:
        return datetime.strptime(self.transform(raw), self.format_string)


class SyslogFormat(TimestampFormat):
    name = "syslog"
    pattern = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b")

    def parse(self, raw: str, year: int) -> datetime:
        return datetime.strptime(f"{year} {raw}", "%Y %b %d %H:%M:%S")


class TimestampParser:
    """Extensible registry of timestamp parsers."""
    def __init__(self, syslog_year: int | None = None) -> None:
        self.syslog_year = syslog_year or datetime.now().year
        self.parsers: list[TimestampFormat] = [
            StrptimeFormat("slash_milliseconds", r"\b\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}:\d{1,6}\b", "%Y/%m/%d %H:%M:%S.%f", lambda x: x.rsplit(":", 1)[0] + "." + x.rsplit(":", 1)[1]),
            StrptimeFormat("iso_t", r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2},\d{1,6}\b", "%Y-%m-%dT%H:%M:%S,%f"),
            StrptimeFormat("standard_comma", r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{1,6}\b", "%Y-%m-%d %H:%M:%S,%f"),
            StrptimeFormat("standard_dot", r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{1,6}\b", "%Y-%m-%d %H:%M:%S.%f"),
            StrptimeFormat("month_name", r"\b\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}\s+\d{2}:\d{2}:\d{2}\b", "%d-%b-%Y %H:%M:%S"),
            SyslogFormat(),
        ]

    def detect_format(self, line: str) -> str | None:
        return next((parser.name for parser in self.parsers if parser.pattern.search(line)), None)

    def extract_timestamp(self, line: str) -> datetime | None:
        for parser in self.parsers:
            try:
                result = parser.extract(line, self.syslog_year)
                if result:
                    return result
            except ValueError:
                continue
        return None

    def normalize(self, dt: datetime) -> datetime:
        return dt.replace(tzinfo=None)


DEFAULT_KEYWORDS = ["ERROR", "WARN", "WARNING", "FAILED", "FAILURE", "FATAL", "SEVERE", "EXCEPTION", "TIMEOUT", "Connection refused", "Cannot", "Unable", "NullPointerException", "IOException", "SQLException", "SocketException", "SSLException", "Access denied", "Permission denied"]
SEVERITY = re.compile(r"\b(ERROR|WARN(?:ING)?|INFO|DEBUG|FATAL|SEVERE)\b", re.I)
THREAD = re.compile(r"\[([^\]]+)\]")
STACK = re.compile(r"^\s*(?:at\s+|Caused by:|\.\.\.\s+\d+\s+more|[\w.$]+(?:Exception|Error):)")


def severity_for(line: str, keywords: list[str]) -> str:
    match = SEVERITY.search(line)
    if match:
        value = match.group(1).upper()
        return "ERROR" if value in {"FATAL", "SEVERE"} else ("WARN" if value == "WARNING" else value)
    return "ERROR" if any(word.lower() in line.lower() for word in keywords) else "UNKNOWN"


def parse_file(path: Path, parser: TimestampParser, keywords: list[str]) -> Iterator[LogEvent]:
    active: LogEvent | None = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for number, raw in enumerate(handle, 1):
            line = raw.rstrip("\n")
            timestamp = parser.extract_timestamp(line)
            if timestamp:
                if active:
                    yield active
                thread_match = THREAD.search(line)
                active = LogEvent(timestamp=timestamp, source_file=str(path), line_number=number, severity=severity_for(line, keywords), thread=thread_match.group(1) if thread_match else None, message=line)
            elif active and (STACK.match(line) or line.startswith(("\t", " "))):
                active.stack_trace = "\n".join(filter(None, [active.stack_trace, line]))
                if "Exception" in line or "Error" in line:
                    active.exception = line.strip()
        if active:
            yield active
