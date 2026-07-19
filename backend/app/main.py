from __future__ import annotations

import io
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse

from .models import InvestigationRequest, InvestigationResult
from .service import investigate

app = FastAPI(title="AI Incident Investigation Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]: return {"status": "ok"}


@app.post("/api/investigations", response_model=InvestigationResult)
def create_investigation(request: InvestigationRequest) -> InvestigationResult:
    try: return investigate(request)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


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

