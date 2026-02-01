from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from .db import init_db, create_archive, list_archives, set_status, get_archive, delete_archive
from .queue import enqueue_capture

app = FastAPI(title="ArchiveIT")

# ---- API models ----
class CreateArchiveBody(BaseModel):
    url: HttpUrl
    kind: str = "article"  # article | video


# ---- API routes ----
@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/archives")
def api_list_archives():
    return list_archives()


@app.post("/api/archive")
def api_create_archive(body: CreateArchiveBody):
    if body.kind not in ("article", "video"):
        raise HTTPException(status_code=400, detail="kind must be 'article' or 'video'")

    rec = create_archive(str(body.url), body.kind)
    enqueue_capture(rec["id"])
    return rec


@app.post("/api/archive/{archive_id}/process")
def api_process_again(archive_id: int):
    rec = get_archive(archive_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Archive not found")
    enqueue_capture(archive_id)
    return {"ok": True}


@app.get("/api/archive/{archive_id}/download")
def api_download(archive_id: int):
    rec = get_archive(archive_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Archive not found")
    path = rec.get("primary_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="File not ready")
    return FileResponse(path, filename=Path(path).name)


@app.delete("/api/archive/{archive_id}")
def api_delete(archive_id: int):
    rec = get_archive(archive_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Archive not found")
    delete_archive(archive_id)
    return {"ok": True}


# ---- Static UI (MUST be LAST so it doesn't swallow /api) ----
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    # API still works even if UI folder is missing
    @app.get("/")
    def _no_ui():
        return {"ok": True, "ui": "missing", "expected": str(STATIC_DIR)}
