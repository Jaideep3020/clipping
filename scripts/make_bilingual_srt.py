#!/usr/bin/env python3
"""
scripts/make_bilingual_srt.py  —  Stage 5.4: Merge English + Chinese into bilingual SRT
Usage: python3 scripts/make_bilingual_srt.py <en_srt> <zh_srt> <output_srt>
Format: English on top, Chinese below (each subtitle block = 2 lines).
"""
import sys, re
from pathlib import Path

SRT_ENTRY = re.compile(
    r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)",
    re.DOTALL,
)

def parse_srt(text: str) -> dict:
    return {
        m.group(1): {"start": m.group(2), "end": m.group(3), "text": m.group(4).strip()}
        for m in SRT_ENTRY.finditer(text.strip() + "\n\n")
    }

en_srt  = Path(sys.argv[1])
zh_srt  = Path(sys.argv[2])
out_srt = Path(sys.argv[3])
out_srt.parent.mkdir(parents=True, exist_ok=True)

en_entries = parse_srt(en_srt.read_text(encoding="utf-8"))
zh_entries = parse_srt(zh_srt.read_text(encoding="utf-8"))

lines = []
for idx in sorted(en_entries.keys(), key=int):
    en = en_entries[idx]
    zh = zh_entries.get(idx)
    lines.append(idx)
    lines.append(f"{en['start']} --> {en['end']}")
    lines.append(en["text"])
    if zh:
        lines.append(zh["text"])
    lines.append("")

out_srt.write_text("\n".join(lines), encoding="utf-8")
print(f"OK: {out_srt}  ({len(en_entries)} entries)")
