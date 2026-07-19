from __future__ import annotations

import io
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


@app.post("/api/export/{format}")
def export(format: str, result: InvestigationResult):
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
