#!/usr/bin/env python3
"""
scripts/smart_edit.py — Autonomous Professional AI Video Editor
================================================================
Takes any raw clip, short, or video and applies the full professional
autonomous editing treatment:
1. Audio intelligence (RMS envelope, speech peaks, transient onsets)
2. PySceneDetect visual shot boundary alignment
3. Dynamic non-repeating transitions (whips, punch zooms, cross zooms, shakes, flashes, glitches)
4. 2-4s Pattern Interrupts: Audio-synced punch zooms and creeping push-ins on static shots
5. Contextual sound design & SFX layer (808 hook drop, whooshes, thuds, transient accents)
6. Cinematic Color Grading (Teal & Orange, Hyper Vibrant, Warm Golden, Moody Filmic, Clean Boost)
7. Atmospheric overlays (35mm subtle grain, impact chromatic aberration)
8. Mobile audio mastering (Highpass 75Hz, EBU R128 -14 LUFS)

Usage:
    python scripts/smart_edit.py <input_video> [output_video] [options]

Options:
    --genre sports|gaming|podcast|solo_talker|viral_general (default: auto-detected)
    --color-grade teal_orange|hyper_vibrant|warm_golden|moody_cinematic|clean_boost (default: auto)
    --no-sfx (disable sound design layer)
    --no-overlays (disable atmospheric grain/chromatic fringe)
    --no-progress-bar (disable bottom progress bar)
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from engine.smart_editor import apply_smart_autonomous_edit


def main():
    parser = argparse.ArgumentParser(description="Autonomous Professional AI Video Editor")
    parser.add_argument("input_video", help="Path to input video file")
    parser.add_argument("output_video", nargs="?", default="", help="Path to output video file (optional)")
    parser.add_argument("--genre", default=None, help="Content genre: sports, gaming, podcast, solo_talker, viral_general")
    parser.add_argument("--color-grade", default=None, help="Color grade preset: teal_orange, hyper_vibrant, warm_golden, moody_cinematic, clean_boost")
    parser.add_argument("--no-sfx", action="store_true", help="Disable sound design layer")
    parser.add_argument("--no-overlays", action="store_true", help="Disable atmospheric film texture overlays")
    parser.add_argument("--no-progress-bar", action="store_true", help="Disable bottom progress bar")
    args = parser.parse_args()

    in_path = Path(args.input_video)
    if not in_path.exists():
        print(f"Error: input video does not exist: {in_path}", file=sys.stderr)
        sys.exit(1)

    if not args.output_video:
        out_path = in_path.parent / f"{in_path.stem}_PRO_EDIT{in_path.suffix}"
    else:
        out_path = Path(args.output_video)

    out_file = apply_smart_autonomous_edit(
        input_video=in_path,
        output_video=out_path,
        title=in_path.stem,
        genre=args.genre,
        color_grade=args.color_grade,
        enable_sfx=not args.no_sfx,
        enable_overlays=not args.no_overlays,
        enable_progress_bar=not args.no_progress_bar,
    )

    print(f"\n🎉 Finished Professional AI Master Edit:")
    print(f"   📁 Output: {out_file.resolve()}\n")


if __name__ == "__main__":
    main()
