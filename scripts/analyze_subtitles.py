#!/usr/bin/env python3
"""
scripts/analyze_subtitles.py  —  Stage 3 helper: Parse VTT → structured JSON
Usage: python3 scripts/analyze_subtitles.py <vtt_path>
Prints JSON: { "text": "...", "entries": [{start, end, text}, ...], "total_duration": N }
"""
import sys, json, re
from pathlib import Path

def parse_vtt(path: str) -> list[dict]:
    """Parse WebVTT file into list of {start, end, text} dicts."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    entries = []

    # Remove WEBVTT header and NOTE blocks
    text = re.sub(r"WEBVTT.*?\n\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"NOTE[^\n]*\n(?:[^\n]*\n)*\n", "", text)

    # Split into cue blocks
    blocks = re.split(r"\n{2,}", text.strip())
    ts_re  = re.compile(
        r"(\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->\s*(\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}"
    )

    def to_secs(ts: str) -> float:
        ts = ts.strip().replace(",", ".")
        parts = ts.split(":")
        if len(parts) == 3:
            return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0])*60 + float(parts[1])
        return float(parts[0])

    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        # Find timestamp line
        for i, line in enumerate(lines):
            if ts_re.search(line):
                arrow_parts = re.split(r"\s*-->\s*", line.split(" -->")[0] + " --> " + line.split("-->")[1].split()[0])
                raw_start = line.split("-->")[0].strip()
                raw_end   = line.split("-->")[1].strip().split()[0]
                # Text is everything after the timestamp line, skip cue ID
                cue_text_lines = lines[i+1:]
                cue_text = " ".join(cue_text_lines)
                # Strip VTT tags like <c>, <00:00:00.000>
                cue_text = re.sub(r"<[^>]+>", "", cue_text).strip()
                if cue_text:
                    entries.append({
                        "start"     : to_secs(raw_start),
                        "end"       : to_secs(raw_end),
                        "start_str" : raw_start,
                        "end_str"   : raw_end,
                        "text"      : cue_text,
                    })
                break

    # Deduplicate overlapping consecutive entries (VTT auto-subs repeat words)
    deduped = []
    for e in entries:
        if deduped and deduped[-1]["text"] == e["text"]:
            deduped[-1]["end"]     = e["end"]
            deduped[-1]["end_str"] = e["end_str"]
        else:
            deduped.append(e)

    return deduped

if __name__ == "__main__":
    vtt_path = sys.argv[1]
    entries  = parse_vtt(vtt_path)

    total_dur = entries[-1]["end"] if entries else 0
    full_text = " ".join(e["text"] for e in entries)

    # Build timestamped transcript for LLM
    ts_lines = []
    for e in entries:
        m = int(e["start"] // 60)
        s = int(e["start"] % 60)
        ts_lines.append(f"[{m:02d}:{s:02d}] {e['text']}")

    result = {
        "entries"       : entries,
        "total_duration": total_dur,
        "count"         : len(entries),
        "text"          : full_text,
        "timestamped"   : "\n".join(ts_lines),
    }
    print(json.dumps(result, ensure_ascii=False))
