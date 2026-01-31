import json
import subprocess
from pathlib import Path
from yt_dlp import YoutubeDL

def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n\n{p.stdout}")

def download_video(url: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Download best video+audio and merge
    ydl_opts = {
        "outtmpl": str(out_dir / "original.%(ext)s"),
        "format": "bv*+ba/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt",
        "postprocessors": [
            {"key": "FFmpegMetadata"},
        ],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Find the downloaded file (original.*)
    originals = list(out_dir.glob("original.*"))
    if not originals:
        raise RuntimeError("yt-dlp did not produce an output file.")
    src = originals[0]

    # Normalize to MP4 (remux/copy when possible, re-encode only if needed)
    mp4_path = out_dir / "archive.mp4"
    if src.suffix.lower() == ".mp4":
        src.replace(mp4_path)
    else:
        # Try remux (fast)
        _run(["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(mp4_path)])
        src.unlink(missing_ok=True)

    # Capture basic metadata
    meta = {
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url") or url,
        "extractor": info.get("extractor"),
        "id": info.get("id"),
    }

    # Save full info json (handy later)
    (out_dir / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    # Subtitles indexable: concatenate any .vtt to text
    vtts = list(out_dir.glob("*.vtt"))
    subs_text = ""
    for v in vtts:
        subs_text += "\n\n" + v.read_text(encoding="utf-8", errors="ignore")

    return {
        "primary_path": str(mp4_path),
        "title": meta.get("title"),
        "meta_json": json.dumps(meta),
        "text_content": subs_text.strip() if subs_text.strip() else None,
        "text_path": str((out_dir / "subtitles.txt")) if subs_text.strip() else None,
    }
