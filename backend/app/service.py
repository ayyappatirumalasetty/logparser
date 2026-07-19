from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from .models import InvestigationRequest, InvestigationResult, LogEvent, safe_path
from .parser import DEFAULT_KEYWORDS, TimestampParser, parse_file

INCLUDE = ("*.log", "*.txt", "tomcat*.*", "DataStoreService*.*", "Apache.log", "management.log", "ArcApp.log", "RPSWebService*")
IGNORE_SUFFIXES = {".bak", ".zip", ".old", ".tmp"}


def discover(root: Path) -> list[Path]:
    files = {item for pattern in INCLUDE for item in root.rglob(pattern) if item.is_file()}
    return sorted(item for item in files if item.suffix.lower() not in IGNORE_SUFFIXES)


def parse_target(value: str, parser: TimestampParser) -> datetime:
    candidate = parser.extract_timestamp(value)
    if candidate:
        return candidate
    for fmt in ("%d.%m.%y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError("Target timestamp is invalid. Try 23.01.26 13:16:11.")


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


def investigate(request: InvestigationRequest) -> InvestigationResult:
    root = safe_path(request.folder_path)
    parser = TimestampParser(request.syslog_year)
    target = parse_target(request.target_timestamp, parser)
    keywords = DEFAULT_KEYWORDS + request.additional_keywords
    files = discover(root)
    def parse_one(path: Path) -> list[LogEvent]:
        try:
            return list(parse_file(path, parser, keywords))
        except OSError:
            return []

    # Each worker streams one file; this avoids holding raw log files in memory.
    all_events: list[LogEvent] = []
    with ThreadPoolExecutor() as executor:
        for events in executor.map(parse_one, files):
            all_events.extend(events)
    all_events.sort(key=lambda event: event.timestamp)
    window = request.window_seconds
    selected = [event for event in all_events if abs((event.timestamp - target).total_seconds()) <= window]
    errors = [event for event in selected if event.severity == "ERROR"]
    warnings = [event for event in selected if event.severity == "WARN"]
    signature = Counter(event.message for event in errors)
    repeated = [{"message": message, "count": count} for message, count in signature.most_common(10)]
    dataset = {"incident": {"target_time": target.isoformat(), "window_seconds": window}, "summary": {"files_scanned": len(files), "events_parsed": len(all_events), "matching_events": len(selected), "errors": len(errors), "warnings": len(warnings)}, "timeline": selected, "exceptions": [event for event in selected if event.exception or event.stack_trace], "affected_files": sorted({event.source_file for event in selected}), "repeated_errors": repeated, "user_context": request.user_context}
    return InvestigationResult(**dataset, report=build_report(dataset))
