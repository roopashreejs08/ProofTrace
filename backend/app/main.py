import io

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader

from .clients.http import ApiClient
from .config import settings
from .llm import LLM
from .memory import Memory
from .orchestrator import Pipeline


app = FastAPI(
    title="ProofTrace",
    version="0.2.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in settings.cors_origins.split(",")
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


memory = Memory()
llm = LLM()

pipeline = Pipeline(
    memory,
    llm,
    lambda inv: ApiClient(memory, inv),
)


class StartRequest(BaseModel):
    text: str = Field(
        min_length=20,
        max_length=settings.max_input_chars,
    )


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ai_enabled": llm.enabled,
        "model": llm.model if llm.enabled else None,
        "max_input_chars": settings.max_input_chars,
        "max_citations": settings.max_citations,
        "full_text_mode": settings.full_text_mode,
    }


@app.post("/api/investigations")
def start(
    req: StartRequest,
    bg: BackgroundTasks,
):
    inv = memory.create_investigation(req.text)

    bg.add_task(
        pipeline.run,
        inv,
    )

    return {
        "id": inv,
    }


@app.get("/api/investigations")
def history():
    return memory.list_investigations()


@app.get("/api/investigations/{inv}")
def get_investigation(inv: str):
    d = memory.get_investigation(inv)

    if not d:
        raise HTTPException(
            404,
            "Investigation not found",
        )

    return d


@app.post("/api/investigations/{inv}/retry")
def retry(inv: str, bg: BackgroundTasks):
    # Re-run a failed (or any) investigation from its stored input text.
    # A fresh investigation is created so the original run is kept in
    # history rather than overwritten.
    text = memory.get_input(inv)

    if not text:
        raise HTTPException(
            404,
            "Investigation not found",
        )

    new_inv = memory.create_investigation(text)

    bg.add_task(
        pipeline.run,
        new_inv,
    )

    return {
        "id": new_inv,
    }


@app.post("/api/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            400,
            "Please upload a PDF file.",
        )

    data = await file.read()

    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(
            413,
            "The PDF is larger than 10 MB.",
        )

    try:
        reader = PdfReader(io.BytesIO(data))

        total_pages = len(reader.pages)
        pages = reader.pages[:settings.max_pdf_pages]

        text = "\n".join(
            (page.extract_text() or "")
            for page in pages
        )

    except Exception:
        raise HTTPException(
            400,
            "Could not read this PDF.",
        )

    if len(text.strip()) < 20:
        raise HTTPException(
            422,
            "No selectable text found. Scanned PDFs need OCR, "
            "which this version does not do.",
        )

    truncated = len(text) > settings.max_input_chars

    return {
        "text": text[:settings.max_input_chars],
        "pages": total_pages,
        "pages_read": len(pages),
        "chars": min(len(text), settings.max_input_chars),
        "truncated": truncated,
    }
