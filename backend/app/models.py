from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    issue_description: str = ""
    environment: str = ""
    operating_system: str = ""
    infrastructure: str = ""
    product_version: str = ""
    recent_changes: str = ""
    symptoms: str = ""
    additional_notes: str = ""


class InvestigationRequest(BaseModel):
    folder_path: str
    target_timestamp: str
    window_seconds: int = Field(default=5, ge=0, le=3600)
    file_patterns: list[str] = Field(default_factory=lambda: ["*.log*", "*.txt"])
    additional_keywords: list[str] = Field(default_factory=list)
    filter_keywords: list[str] = Field(default_factory=list)
    syslog_year: int | None = None
    user_context: UserContext = Field(default_factory=UserContext)


class LogEvent(BaseModel):
    timestamp: datetime
    source_file: str
    line_number: int
    severity: Literal["ERROR", "WARN", "INFO", "DEBUG", "UNKNOWN"] = "UNKNOWN"
    thread: str | None = None
    component: str | None = None
    message: str
    exception: str | None = None
    stack_trace: str | None = None


class Progress(BaseModel):
    stage: str
    files_found: int = 0
    files_parsed: int = 0
    current_file: str | None = None
    percentage: int = 0
    elapsed_seconds: float = 0
    estimated_remaining_seconds: float | None = None


class InvestigationResult(BaseModel):
    incident: dict
    summary: dict
    timeline: list[LogEvent]
    exceptions: list[LogEvent]
    affected_files: list[str]
    repeated_errors: list[dict]
    user_context: UserContext
    report: str


class SupportRequest(BaseModel):
    """The filtered Entries TXT content and optional human issue context."""

    entries_txt: str = Field(min_length=1, max_length=300_000)
    issue_context: str = Field(default="", max_length=12_000)


class SupportResponse(BaseModel):
    troubleshooting_steps: str
    model: str


def safe_path(path: str) -> Path:
    """Resolve user supplied paths, rejecting invalid/unavailable folders."""
    import os
    if os.name != 'nt':
        normalized = path.replace('\\', '/')
        if 'loganalyser/demo/generated' in normalized:
            path = '/app/demo/generated'
        elif 'loganalyser/temptes' in normalized:
            path = '/app/temptes'
            
    target = Path(path).expanduser().resolve()
    if not target.is_dir():
        raise ValueError(f"Folder path must point to an accessible directory: {path}")
    return target
