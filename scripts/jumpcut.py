#!/usr/bin/env python3
"""
jumpcut.py — Remove silences from a video (jump-cut edit)
From the video-clipping skill §4.8.

Usage:
    python3 scripts/jumpcut.py <input> <output> [noise_dB] [min_silence_s] [pad_s]

Examples:
    python3 scripts/jumpcut.py source/video.mp4 output/jumpcut.mp4
    python3 scripts/jumpcut.py source/video.mp4 output/jumpcut.mp4 -25dB 0.5 0.1
"""
import re, subprocess, sys, os, tempfile

src, out = sys.argv[1], sys.argv[2]
noise   = sys.argv[3] if len(sys.argv) > 3 else "-30dB"
min_sil = float(sys.argv[4]) if len(sys.argv) > 4 else 0.4
pad     = float(sys.argv[5]) if len(sys.argv) > 5 else 0.08

# Get total duration
dur = float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "csv=p=0", src]).decode().strip())

# Detect silences
r = subprocess.run(
    ["ffmpeg", "-hide_banner", "-i", src, "-af",
     f"silencedetect=noise={noise}:d={min_sil}", "-f", "null", "-"],
    capture_output=True, text=True)

starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
ends   = [float(x) for x in re.findall(r"silence_end: ([\d.]+)",   r.stderr)]

if len(starts) > len(ends):
    ends.append(dur)

# Build speech segments
keep, cur = [], 0.0
for s, e in zip(starts, ends):
    if s - cur > 0.05:
        keep.append((max(0.0, cur), min(dur, s + pad)))
    cur = max(0.0, e - pad)
if dur - cur > 0.05:
    keep.append((cur, dur))

if not keep:
    sys.exit("No speech segments found. Try a higher noise threshold (e.g. -25dB).")

print(f"  Keeping {len(keep)} segments, removing ~{dur - sum(b-a for a,b in keep):.1f}s of silence.")

# Build filter_complex
parts, labels = [], ""
for i, (a, b) in enumerate(keep):
    parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
    parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
    labels += f"[v{i}][a{i}]"
parts.append(f"{labels}concat=n={len(keep)}:v=1:a=1[v][a]")

with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
    f.write(";\n".join(parts))
    script = f.name

subprocess.check_call([
    "ffmpeg", "-hide_banner", "-y", "-i", src,
    "-filter_complex_script", script,
    "-map", "[v]", "-map", "[a]",
    "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart", out
])
os.unlink(script)
print(f"  ✓ Done → {out}")
