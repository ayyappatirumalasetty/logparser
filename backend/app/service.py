from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Callable

from .models import InvestigationRequest, InvestigationResult, LogEvent, Progress, safe_path
from .parser import DEFAULT_KEYWORDS, TimestampParser, parse_file

INCLUDE = ("*.log*", "*.txt")
IGNORE_SUFFIXES = {".bak", ".zip", ".old", ".tmp"}


def discover(root: Path, patterns: list[str] | None = None) -> list[Path]:
    raw_patterns = patterns or INCLUDE
    active_patterns = []
    for p in raw_patterns:
        for sub_p in p.split(','):
            cleaned = sub_p.strip()
            if cleaned:
                active_patterns.append(cleaned)
    if not active_patterns:
        raise ValueError("Provide at least one file pattern, for example *.log*.")
    files = {item for pattern in active_patterns for item in root.rglob(pattern) if item.is_file()}
    return sorted(item for item in files if item.suffix.lower() not in IGNORE_SUFFIXES)


def parse_target(value: str, parser: TimestampParser) -> datetime:
    candidate = parser.extract_timestamp(value)
    if candidate:
        return candidate
    # datetime-local input sends ISO 8601; keep legacy formats for CLI/API callers.
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in (
        "%Y/%m/%d %H:%M:%S", "%d.%m.%y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y %I:%M:%S %p", "%Y/%m/%d %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError("Target timestamp is invalid. Use 2026-07-18T05:55:36 or 2026/07/18 05:55:36.")


def build_report(dataset: dict) -> str:
    summary = dataset["summary"]
    repeated = dataset["repeated_errors"]
    headline = repeated[0]["message"] if repeated else "No repeated error signature was identified in the selected window."
    return f"""# Incident Investigation Report

## Executive Summary
Analysed {summary['matching_events']} matching events from {summary['files_scanned']} discovered files around {dataset['incident']['target_time']}. {summary['errors']} error-level and {summary['warnings']} warning-level events were observed.

## Timeline Summary
Events are presented chronologically below. Focus investigation on the earliest error and its preceding warning or dependency failure.

## Most Probable Root Cause
{headline}

## Supporting Evidence
{len(dataset['exceptions'])} exception-bearing events were captured across {len(dataset['affected_files'])} affected files.

## Confidence Level
Medium — this is derived from local log correlation in the configured time window.

## Recommended Troubleshooting Steps
1. Validate the first error's dependent service, endpoint, credentials, and network path.
2. Compare timestamps with recent deployment, configuration, or infrastructure changes.
3. Collect adjacent logs using a wider window if the triggering event is absent.

## Additional Diagnostic Checks
Review repeated errors, thread names, connection pools, disk capacity, and service health metrics.
"""


def investigate(request: InvestigationRequest, on_progress: Callable[[Progress], None] | None = None) -> InvestigationResult:
    started = monotonic()
    def progress(stage: str, files_found: int, files_parsed: int = 0, current_file: str | None = None) -> None:
        if not on_progress:
            return
        elapsed = monotonic() - started
        percentage = int(files_parsed / files_found * 100) if files_found else 0
        remaining = ((elapsed / files_parsed) * (files_found - files_parsed)) if files_parsed else None
        on_progress(Progress(stage=stage, files_found=files_found, files_parsed=files_parsed, current_file=current_file, percentage=percentage, elapsed_seconds=round(elapsed, 1), estimated_remaining_seconds=round(remaining, 1) if remaining is not None else None))

    root = safe_path(request.folder_path)
    parser = TimestampParser(request.syslog_year)
    target = parse_target(request.target_timestamp, parser)
    keywords = DEFAULT_KEYWORDS + request.additional_keywords
    progress("Scanning files", 0)
    files = discover(root, request.file_patterns)
    progress("Parsing logs", len(files))
    def parse_one(path: Path) -> list[LogEvent]:
        try:
            return list(parse_file(path, parser, keywords))
        except OSError:
            return []

    # Each worker streams one file; this avoids holding raw log files in memory.
    all_events: list[LogEvent] = []
    with ThreadPoolExecutor() as executor:
        for index, (path, events) in enumerate(zip(files, executor.map(parse_one, files)), 1):
            all_events.extend(events)
            progress("Parsing logs", len(files), index, str(path))
    all_events.sort(key=lambda event: event.timestamp)
    window = request.window_seconds
    if window == 0:
        target_sec = target.replace(microsecond=0)
        selected = [event for event in all_events if event.timestamp.replace(microsecond=0) == target_sec]
    else:
        selected = [event for event in all_events if abs((event.timestamp - target).total_seconds()) <= window]

    filter_keywords = [kw.strip().lower() for kw in request.filter_keywords if kw.strip()]
    if filter_keywords:
        selected = [event for event in selected if any(kw in event.message.lower() for kw in filter_keywords)]

    errors = [event for event in selected if event.severity == "ERROR"]
    warnings = [event for event in selected if event.severity == "WARN"]
    signature = Counter(event.message for event in errors)
    repeated = [{"message": message, "count": count} for message, count in signature.most_common(10)]
    dataset = {"incident": {"target_time": target.isoformat(), "window_seconds": window}, "summary": {"files_scanned": len(files), "events_parsed": len(all_events), "matching_events": len(selected), "errors": len(errors), "warnings": len(warnings)}, "timeline": selected, "exceptions": [event for event in selected if event.exception or event.stack_trace], "affected_files": sorted({event.source_file for event in selected}), "repeated_errors": repeated, "user_context": request.user_context}
    progress("Complete", len(files), len(files))
    return InvestigationResult(**dataset, report=build_report(dataset))
