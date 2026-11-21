#!/usr/bin/env python3
"""
scripts/burn_viral_subtitles.py — Standalone Viral Subtitle & Hook Banner Tool
=============================================================================
Usage:
    python scripts/burn_viral_subtitles.py <video_in> <words_json_or_vtt> <video_out> [options]

Options:
    --style hormozi|mrbeast|neon|minimal (default: hormozi)
    --hook-banner "TITLE" (optional top hook headline badge)
    --framing blur_bg|center_crop|none (default: none)
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from engine.viral_subtitles import burn_viral_subtitles
from engine.viral_editor import add_hook_banner_to_video, reframe_video_9_16, assemble_viral_clip


def load_words(path_str: str) -> list[dict]:
    p = Path(path_str)
    if not p.exists():
        return []
    if p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # check segments or words
            words = []
            for seg in data.get("segments", []):
                words.extend(seg.get("words", []))
            return words
    elif p.suffix == ".vtt":
        # Parse VTT entries as words/cues
        sys.path.insert(0, str(ROOT_DIR / "scripts"))
        from analyze_subtitles import parse_vtt
        cues = parse_vtt(str(p))
        words = []
        for c in cues:
            # Split cue into estimated word timestamps
            w_list = c["text"].split()
            dur = c["end"] - c["start"]
            w_dur = dur / max(1, len(w_list))
            for i, w in enumerate(w_list):
                words.append({
                    "word": w,
                    "start": c["start"] + i * w_dur,
                    "end": c["start"] + (i + 1) * w_dur,
                })
        return words
    return []


def main():
    parser = argparse.ArgumentParser(description="Burn dynamic viral subtitles and hook banners")
    parser.add_argument("video_in", help="Input video file")
    parser.add_argument("transcript_in", help="Whisper JSON or VTT subtitle file")
    parser.add_argument("video_out", help="Output video file")
    parser.add_argument("--style", default="hormozi", choices=["hormozi", "mrbeast", "neon", "minimal"], help="Caption preset style")
    parser.add_argument("--hook-banner", default="", help="Optional top hook headline")
    parser.add_argument("--framing", default="none", choices=["blur_bg", "center_crop", "none"], help="Framing mode")
    args = parser.parse_args()

    print(f"Loading words from {args.transcript_in} ...")
    words = load_words(args.transcript_in)
    print(f"Loaded {len(words)} word cues.")

    print(f"Processing viral video -> {args.video_out} ...")
    assemble_viral_clip(
        source_video=Path(args.video_in),
        output_path=Path(args.video_out),
        start_sec=0.0,
        end_sec=999999.0,  # Full clip
        hook_title=args.hook_banner,
        words=words,
        framing_mode=args.framing,
        caption_style=args.style,
        add_hook_banner=bool(args.hook_banner),
    )
    print(f"✅ Finished! Saved to {args.video_out}")


if __name__ == "__main__":
    main()
