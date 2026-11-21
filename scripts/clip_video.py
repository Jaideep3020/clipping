#!/usr/bin/env python3
"""
scripts/clip_video.py  —  Stage 5.1: Clip a video segment with FFmpeg
Usage: python3 scripts/clip_video.py <video_path> <start_time> <end_time> <output_path>
       Times in HH:MM:SS or MM:SS or float seconds.
"""
import sys, subprocess, re
from pathlib import Path

def to_secs(t: str) -> float:
    t = t.strip()
    if re.match(r"^\d+(\.\d+)?$", t):
        return float(t)
    parts = t.split(":")
    if len(parts) == 3:
        return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
    return int(parts[0])*60 + float(parts[1])

src      = sys.argv[1]
start    = to_secs(sys.argv[2])
end      = to_secs(sys.argv[3])
out_path = Path(sys.argv[4])
out_path.parent.mkdir(parents=True, exist_ok=True)

duration = end - start

# Check for Apple VideoToolbox (fast HW on Mac)
probe = subprocess.run(
    ["ffmpeg", "-hide_banner", "-encoders"],
    capture_output=True, text=True
)
use_hw = "h264_videotoolbox" in probe.stdout

if use_hw:
    vcodec_args = ["-c:v", "h264_videotoolbox", "-q:v", "60"]
else:
    vcodec_args = ["-c:v", "libx264", "-crf", "18", "-preset", "fast"]

cmd = [
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
    "-ss", str(start),
    "-i", src,
    "-t", str(duration),
    *vcodec_args,
    "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart",
    str(out_path),
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    # Fallback to libx264
    cmd_sw = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(start), "-i", src, "-t", str(duration),
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    r2 = subprocess.run(cmd_sw, capture_output=True, text=True)
    if r2.returncode != 0:
        print(f"ERROR: {r2.stderr}", file=sys.stderr)
        sys.exit(1)

size = out_path.stat().st_size if out_path.exists() else 0
print(f"OK: {out_path}  ({size/1_048_576:.1f} MB)")
