#!/usr/bin/env python3
"""
scripts/burn_subtitles.py  —  Stage 5.5: Burn SRT subtitles into video
Skill tech note: uses a temp dir with no spaces in path to avoid FFmpeg subtitles filter bug.
Usage: python3 scripts/burn_subtitles.py <video_path> <srt_path> <output_path>
Prefers ffmpeg-full (libass); falls back to standard ffmpeg with drawtext workaround.
"""
import sys, subprocess, shutil, tempfile, os
from pathlib import Path

def find_ffmpeg() -> str:
    """Return path to ffmpeg binary with libass support if available."""
    ffmpeg_full = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
    if Path(ffmpeg_full).exists():
        # Verify it has the subtitles filter
        r = subprocess.run([ffmpeg_full, "-filters"], capture_output=True, text=True)
        if "subtitles" in r.stdout + r.stderr:
            return ffmpeg_full
    return "ffmpeg"  # system default

video_path  = Path(sys.argv[1])
srt_path    = Path(sys.argv[2])
output_path = Path(sys.argv[3])
output_path.parent.mkdir(parents=True, exist_ok=True)

ffmpeg_bin = find_ffmpeg()

# ── Use temp dir to avoid spaces-in-path problem (skill tech note §1) ────────
with tempfile.TemporaryDirectory(prefix="clip_burn_") as tmp:
    tmp_video = os.path.join(tmp, "v.mp4")
    tmp_srt   = os.path.join(tmp, "s.srt")
    tmp_out   = os.path.join(tmp, "out.mp4")

    shutil.copy2(str(video_path), tmp_video)
    shutil.copy2(str(srt_path),   tmp_srt)

    # Escape the temp SRT path for FFmpeg filter (colons on Windows need escaping)
    escaped = tmp_srt.replace("\\", "/").replace(":", "\\:")

    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-i", tmp_video,
        "-vf",
        (f"subtitles={escaped}:force_style='"
         "FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,"
         "OutlineColour=&H00000000,BorderStyle=1,Outline=2,"
         "Shadow=0,Alignment=2,MarginV=30'"),
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        tmp_out,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        shutil.move(tmp_out, str(output_path))
        size = output_path.stat().st_size
        print(f"OK: {output_path}  ({size/1_048_576:.1f} MB)")
    else:
        # Fallback: copy video and attach as soft subtitle instead
        print(f"⚠  libass burn failed; attaching as soft subtitle instead.")
        cmd_soft = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_path),
            "-i", str(srt_path),
            "-c:v", "copy", "-c:a", "copy",
            "-c:s", "mov_text",
            str(output_path),
        ]
        r2 = subprocess.run(cmd_soft, capture_output=True, text=True)
        if r2.returncode != 0:
            print(f"ERROR: {result.stderr}\n{r2.stderr}", file=sys.stderr)
            sys.exit(1)
        print(f"OK (soft sub): {output_path}")
