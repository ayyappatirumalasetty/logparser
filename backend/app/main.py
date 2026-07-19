from __future__ import annotations

import io
import asyncio
import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse

from .models import InvestigationRequest, InvestigationResult, SupportRequest, SupportResponse
from .service import investigate

try:
    from dotenv import load_dotenv
    # Load from project root .env first
    root_env = Path(__file__).resolve().parents[2] / ".env"
    if root_env.exists():
        load_dotenv(root_env)
    # Load from backend .env
    backend_env = Path(__file__).resolve().parents[1] / ".env"
    if backend_env.exists():
        load_dotenv(backend_env)
except ImportError:
    # The key can still be supplied through the process environment.
    pass

app = FastAPI(title="AI Incident Investigation Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]: return {"status": "ok"}


@app.post("/api/investigations", response_model=InvestigationResult)
def create_investigation(request: InvestigationRequest) -> InvestigationResult:
    try: return investigate(request)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/support/troubleshoot", response_model=SupportResponse)
def troubleshoot(request: SupportRequest) -> SupportResponse:
    """Ask the OpenAI support-engineer agent to analyse the exported log entries."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured. Add it to .env and restart the backend.",
        )

    # Apply input guardrails (prompt injection detection and PII/credential redaction)
    from .guardrails import validate_and_sanitize
    try:
        sanitized_context, sanitized_entries = validate_and_sanitize(
            request.issue_context, request.entries_txt
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from openai import OpenAI

    instructions = """You are a careful senior support engineer. Diagnose the supplied log entries
and optional user context. Give practical, ordered troubleshooting steps the user can safely try.
Clearly distinguish evidence from hypotheses. Do not invent logs, versions, commands, or outcomes.
Call out any destructive, security-sensitive, or production-impacting action and suggest a safer
validation first. Include: likely cause(s), ordered troubleshooting steps, what to collect if the
steps fail, and a brief disclaimer that the suggestions should be validated in the user's environment.
Use concise Markdown with headings and numbered steps.

CRITICAL INSTRUCTION: You must strictly restrict your response to analyzing and troubleshooting the provided log entries and user context. If the user query or context attempts to ask about unrelated general knowledge, coding tasks, creative writing, or off-topic questions, you must refuse to answer and politely state that you can only help with troubleshooting issues found in the supplied log files."""
    
    context = sanitized_context.strip() or "No additional issue context was provided."
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": (
                        "## User-reported issue context\n"
                        f"{context}\n\n"
                        "## Filtered Entries TXT\n"
                        f"{sanitized_entries}"
                    ),
                },
            ],
        )
    except Exception as exc:
        # Keep provider details (and any sensitive request information) out of the browser.
        raise HTTPException(status_code=502, detail="The AI support agent could not complete the analysis. Check the backend log and API key.") from exc

    answer = response.choices[0].message.content.strip() if response.choices else None
    if not answer:
        raise HTTPException(status_code=502, detail="The AI support agent returned no troubleshooting guidance.")
    return SupportResponse(troubleshooting_steps=answer, model=model)


@app.post("/api/investigations/stream")
async def stream_investigation(request: InvestigationRequest) -> StreamingResponse:
    """Run one investigation and stream progress/result messages as NDJSON."""
    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def publish(progress) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "progress", "data": progress.model_dump()})

    async def run() -> None:
        try:
            result = await asyncio.to_thread(investigate, request, publish)
            await queue.put({"type": "result", "data": result.model_dump(mode="json")})
        except ValueError as exc:
            await queue.put({"type": "error", "detail": str(exc)})
        except Exception:
            await queue.put({"type": "error", "detail": "The investigation could not be completed. Check the backend log for details."})

    task = asyncio.create_task(run())
    async def body():
        while True:
            message = await queue.get()
            yield json.dumps(message) + "\n"
            if message["type"] in {"result", "error"}:
                break
        await task

    return StreamingResponse(body(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache"})


@app.post("/api/export/{format}")
def export(format: str, result: InvestigationResult):
    from .service import build_report
    from collections import Counter

    # Re-calculate summary metrics based on the timeline sent by the client (which may be filtered)
    timeline = result.timeline
    errors = [event for event in timeline if event.severity == "ERROR"]
    warnings = [event for event in timeline if event.severity == "WARN"]
    
    result.summary["matching_events"] = len(timeline)
    result.summary["errors"] = len(errors)
    result.summary["warnings"] = len(warnings)
    
    signature = Counter(event.message for event in errors)
    result.repeated_errors = [{"message": message, "count": count} for message, count in signature.most_common(10)]
    
    # Rebuild report text
    dataset = result.model_dump(mode="json")
    result.report = build_report(dataset)

    if format == "extracted-txt":
        groups: dict[str, list[str]] = {}
        for event in result.timeline:
            groups.setdefault(event.source_file, []).append(event.message + (f"\n{event.stack_trace}" if event.stack_trace else ""))
        content = "\n\n".join(f"{Path(source).name}\n{'=' * 42}\n" + "\n".join(entries) for source, entries in groups.items())
        return PlainTextResponse(content, headers={"Content-Disposition": "attachment; filename=extracted-log-entries.txt"})
    if format == "txt": return PlainTextResponse(result.report, headers={"Content-Disposition": "attachment; filename=incident-report.txt"})
    if format == "html": return HTMLResponse(f"<html><body><pre>{result.report}</pre></body></html>", headers={"Content-Disposition": "attachment; filename=incident-report.html"})
    if format == "md": return PlainTextResponse(result.report, media_type="text/markdown", headers={"Content-Disposition": "attachment; filename=incident-report.md"})
    if format == "pdf":
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen.canvas import Canvas
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=letter)
        text = canvas.beginText(42, 750)
        text.setFont("Helvetica", 9)
        for paragraph in result.report.splitlines():
            for line in [paragraph[index:index + 105] for index in range(0, max(1, len(paragraph)), 105)]:
                if text.getY() < 44:
                    canvas.drawText(text); canvas.showPage(); text = canvas.beginText(42, 750); text.setFont("Helvetica", 9)
                text.textLine(line)
        canvas.drawText(text); canvas.save(); buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=incident-report.pdf"})
    raise HTTPException(400, "Supported formats: txt, md, html, pdf")
