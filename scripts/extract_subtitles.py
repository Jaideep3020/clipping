#!/usr/bin/env python3
"""
scripts/extract_subtitles.py  —  Stage 5.2: Slice subtitle entries for a time range
Usage: python3 scripts/extract_subtitles.py <vtt_path> <start_secs> <end_secs> <output_srt>
Outputs SRT file with timestamps re-based to 00:00:00.
"""
import sys, re, json
from pathlib import Path

# Reuse the VTT parser from analyze_subtitles
sys.path.insert(0, str(Path(__file__).parent))
from analyze_subtitles import parse_vtt

def secs_to_srt(s: float) -> str:
    s   = max(0.0, s)
    h   = int(s // 3600)
    m   = int((s % 3600) // 60)
    sec = s % 60
    ms  = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{int(sec):02d},{ms:03d}"

vtt_path  = sys.argv[1]
start_sec = float(sys.argv[2])
end_sec   = float(sys.argv[3])
out_srt   = Path(sys.argv[4])
out_srt.parent.mkdir(parents=True, exist_ok=True)

entries = parse_vtt(vtt_path)

# Filter to the requested window
window = [
    e for e in entries
    if e["end"] > start_sec and e["start"] < end_sec
]

# Re-base timestamps
lines = []
for idx, e in enumerate(window, 1):
    t_start = max(0.0, e["start"] - start_sec)
    t_end   = max(0.0, e["end"]   - start_sec)
    lines.append(str(idx))
    lines.append(f"{secs_to_srt(t_start)} --> {secs_to_srt(t_end)}")
    lines.append(e["text"])
    lines.append("")

out_srt.write_text("\n".join(lines), encoding="utf-8")
print(f"OK: {out_srt}  ({len(window)} entries)")
