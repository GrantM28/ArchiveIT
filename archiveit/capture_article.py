import json
from pathlib import Path
from datetime import datetime, timezone

import trafilatura
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _extract_text(html: str) -> str:
    # 1) Try high-quality article extraction
    extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
    if extracted and extracted.strip():
        return extracted.strip()

    # 2) Fallback: plain text from soup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split()).strip()

def _auto_scroll(page, max_scrolls: int = 30):
    # Helps with X/Twitter threads, infinite scroll pages, etc.
    for _ in range(max_scrolls):
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)

def capture_page(url: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="ArchiveIT/1.0 (Headless Chromium)",
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(1000)
        _auto_scroll(page)
        page.wait_for_load_state("networkidle", timeout=60_000)

        title = page.title().strip() if page.title() else None

        # Save artifacts
        html = page.content()
        (out_dir / "page.html").write_text(html, encoding="utf-8", errors="ignore")

        pdf_path = out_dir / "snapshot.pdf"
        page.pdf(path=str(pdf_path), format="A4", print_background=True)

        png_path = out_dir / "snapshot.png"
        page.screenshot(path=str(png_path), full_page=True)

        browser.close()

    text = _extract_text(html)
    text_path = out_dir / "content.txt"
    text_path.write_text(text, encoding="utf-8", errors="ignore")

    meta = {
        "title": title,
        "captured_at": utc_now_iso(),
        "source_url": url,
        "artifacts": {
            "pdf": str(pdf_path),
            "screenshot": str(png_path),
            "html": str(out_dir / "page.html"),
            "text": str(text_path),
        },
    }

    return {
        "primary_path": str(pdf_path),
        "title": title,
        "meta_json": json.dumps(meta),
        "text_content": text,
        "text_path": str(text_path),
    }
