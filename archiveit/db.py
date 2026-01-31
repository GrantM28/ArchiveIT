import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone

from .settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS archives (
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  kind TEXT NOT NULL,              -- 'video' | 'page'
  title TEXT,
  status TEXT NOT NULL,            -- 'QUEUED'|'RUNNING'|'DONE'|'ERROR'
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  out_dir TEXT NOT NULL,
  primary_path TEXT,               -- mp4 OR pdf
  text_path TEXT,                  -- extracted text file (for search)
  meta_json TEXT                   -- json string (yt-dlp info or page info)
);

CREATE VIRTUAL TABLE IF NOT EXISTS archives_fts USING fts5(
  id UNINDEXED,
  title,
  content,
  tokenize='porter'
);
"""

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def init_db() -> None:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()

def upsert_fts(conn: sqlite3.Connection, archive_id: str, title: str | None, content: str | None) -> None:
    conn.execute("DELETE FROM archives_fts WHERE id = ?", (archive_id,))
    conn.execute(
        "INSERT INTO archives_fts (id, title, content) VALUES (?, ?, ?)",
        (archive_id, title or "", content or "")
    )

def create_archive(conn: sqlite3.Connection, archive_id: str, url: str, kind: str, out_dir: str) -> None:
    now = utc_now_iso()
    conn.execute(
        """INSERT INTO archives (id, url, kind, status, created_at, updated_at, out_dir)
           VALUES (?, ?, ?, 'QUEUED', ?, ?, ?)""",
        (archive_id, url, kind, now, now, out_dir)
    )

def update_archive(conn: sqlite3.Connection, archive_id: str, **fields) -> None:
    fields["updated_at"] = utc_now_iso()
    keys = list(fields.keys())
    sets = ", ".join([f"{k} = ?" for k in keys])
    values = [fields[k] for k in keys]
    values.append(archive_id)
    conn.execute(f"UPDATE archives SET {sets} WHERE id = ?", values)
