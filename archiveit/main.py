import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from .settings import settings
from .db import init_db, db, create_archive, update_archive
from .queue import get_queue
from .tasks import process_archive, guess_kind

app = FastAPI(title="ArchiveIT", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.on_event("startup")
def _startup():
    init_db()
    (Path(settings.data_dir) / "archives").mkdir(parents=True, exist_ok=True)

class ArchiveRequest(BaseModel):
    url: HttpUrl
    kind: str | None = None  # 'video' or 'page' or None (auto)

@app.post("/api/archive")
def submit_archive(req: ArchiveRequest):
    archive_id = str(uuid4())
    kind = req.kind or guess_kind(str(req.url))

    out_dir = str(Path(settings.data_dir) / "archives" / archive_id)

    with db() as conn:
        create_archive(conn, archive_id, str(req.url), kind, out_dir)
        conn.commit()

    q = get_queue()
    q.enqueue(process_archive, archive_id, str(req.url), kind)

    return {"id": archive_id, "status": "QUEUED", "kind": kind, "url": str(req.url)}

@app.get("/api/archive/{archive_id}")
def get_archive(archive_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM archives WHERE id = ?", (archive_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Not found")
        data = dict(row)
        if data.get("meta_json"):
            try:
                data["meta"] = json.loads(data["meta_json"])
            except Exception:
                data["meta"] = None
        return data

@app.get("/api/archives")
def list_archives(
    q: str | None = Query(default=None, description="full text search"),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with db() as conn:
        params = []
        where = []
        if status:
            where.append("a.status = ?")
            params.append(status)

        if q:
            # FTS join
            sql = f"""
              SELECT a.*
              FROM archives a
              JOIN archives_fts f ON f.id = a.id
              WHERE archives_fts MATCH ?
              {"AND " + " AND ".join(where) if where else ""}
              ORDER BY a.created_at DESC
              LIMIT ? OFFSET ?
            """
            params2 = [q] + params + [limit, offset]
            rows = conn.execute(sql, params2).fetchall()
        else:
            sql = f"""
              SELECT a.*
              FROM archives a
              {"WHERE " + " AND ".join(where) if where else ""}
              ORDER BY a.created_at DESC
              LIMIT ? OFFSET ?
            """
            params2 = params + [limit, offset]
            rows = conn.execute(sql, params2).fetchall()

        return [dict(r) for r in rows]

@app.get("/api/archive/{archive_id}/download")
def download_primary(archive_id: str):
    with db() as conn:
        row = conn.execute("SELECT primary_path, title, kind FROM archives WHERE id = ?", (archive_id,)).fetchone()
        if not row or not row["primary_path"]:
            raise HTTPException(404, "File not ready")
        path = Path(row["primary_path"])
        if not path.exists():
            raise HTTPException(404, "File missing on disk")

        # Friendly filename
        title = (row["title"] or archive_id).strip().replace("/", "-")
        ext = path.suffix
        filename = f"{title}{ext}"

        return FileResponse(str(path), filename=filename)

@app.delete("/api/archive/{archive_id}")
def delete_archive(archive_id: str):
    if not settings.allow_delete:
        raise HTTPException(403, "Delete disabled")

    with db() as conn:
        row = conn.execute("SELECT out_dir FROM archives WHERE id = ?", (archive_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Not found")

        out_dir = Path(row["out_dir"])
        conn.execute("DELETE FROM archives_fts WHERE id = ?", (archive_id,))
        conn.execute("DELETE FROM archives WHERE id = ?", (archive_id,))
        conn.commit()

    shutil.rmtree(out_dir, ignore_errors=True)
    return {"ok": True}
