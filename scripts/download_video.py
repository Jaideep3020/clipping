#!/usr/bin/env python3
"""
scripts/download_video.py  —  Stage 2: Download video + subtitles
Usage: python3 scripts/download_video.py <youtube_url> [output_dir]
Outputs:
  source/<id>.mp4
  source/<id>.en.vtt   (manual or auto captions)
"""
import sys, json
from pathlib import Path
import yt_dlp

BASE   = Path(__file__).parent.parent
SOURCE = BASE / "source"
SOURCE.mkdir(parents=True, exist_ok=True)

url = sys.argv[1]
out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else SOURCE

# ── Download video (subtitles optional, never fail if 429) ────────────────────
ydl_opts = {
    "format"              : "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "merge_output_format" : "mp4",
    "outtmpl"             : str(out_dir / "%(id)s.%(ext)s"),
    "writesubtitles"      : False,
    "writeautomaticsub"   : False,
    "overwrites"          : False,
    "quiet"               : False,
    "no_warnings"         : True,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=True)

vid   = info["id"]
title = info.get("title", vid)
dur   = info.get("duration", 0)
size  = next(
    (Path(out_dir / f"{vid}.mp4").stat().st_size
     for _ in [1] if (out_dir / f"{vid}.mp4").exists()), 0
)

# Find subtitle file (may be .en.vtt or .en-orig.vtt etc.)
vtt_candidates = list(out_dir.glob(f"{vid}*.vtt"))
vtt_path = str(vtt_candidates[0]) if vtt_candidates else ""

result = {
    "id"       : vid,
    "title"    : title,
    "duration" : dur,
    "size_bytes": size,
    "video_path": str(out_dir / f"{vid}.mp4"),
    "vtt_path"  : vtt_path,
}
print(json.dumps(result, ensure_ascii=False))
