import json
from pathlib import Path
from urllib.parse import urlparse

from .db import db, update_archive, upsert_fts
from .settings import settings
from .capture_video import download_video
from .capture_article import capture_page

VIDEO_HOSTS = {
    "youtube.com", "www.youtube.com", "youtu.be",
    "vimeo.com", "www.vimeo.com",
    "tiktok.com", "www.tiktok.com",
}

def guess_kind(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host in VIDEO_HOSTS:
        return "video"
    # Common direct media URLs
    lower = url.lower()
    if any(lower.endswith(ext) for ext in [".mp4", ".mkv", ".mov", ".webm", ".mp3", ".m4a"]):
        return "video"
    return "page"

def process_archive(archive_id: str, url: str, kind: str | None = None) -> None:
    kind = kind or guess_kind(url)

    out_dir = Path(settings.data_dir) / "archives" / archive_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with db() as conn:
        update_archive(conn, archive_id, status="RUNNING")
        conn.commit()

    try:
        if kind == "video":
            result = download_video(url, out_dir)
        else:
            result = capture_page(url, out_dir)

        title = result.get("title")
        meta_json = result.get("meta_json")
        primary_path = result.get("primary_path")
        text_content = result.get("text_content")
        text_path = result.get("text_path")

        # If we have extracted text, write it to disk (even if it came from subs)
        if text_content and text_path:
            Path(text_path).write_text(text_content, encoding="utf-8", errors="ignore")

        with db() as conn:
            update_archive(
                conn,
                archive_id,
                kind=kind,
                title=title,
                status="DONE",
                error=None,
                primary_path=primary_path,
                text_path=text_path,
                meta_json=meta_json,
            )
            upsert_fts(conn, archive_id, title, text_content)
            conn.commit()

    except Exception as e:
        with db() as conn:
            update_archive(conn, archive_id, status="ERROR", error=str(e))
            conn.commit()
        raise
