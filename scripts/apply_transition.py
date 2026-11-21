#!/usr/bin/env python3
"""
scripts/apply_transition.py
===========================
CLI tool to apply the complete transition pack suite (CapCut & Premiere Pro)
to video clips, either between two separate clips or across internal cuts of a single video.

Usage:
  # 1. List all 28 transitions and 6 packs:
  python3 scripts/apply_transition.py --list

  # 2. Join 2 clips with a CapCut Whip Left transition and synced Whoosh SFX:
  python3 scripts/apply_transition.py --clip-a clip1.mp4 --clip-b clip2.mp4 -o out.mp4 --transition whip_left

  # 3. Join 2 clips with a Premiere Cross Dissolve:
  python3 scripts/apply_transition.py --clip-a clip1.mp4 --clip-b clip2.mp4 -o out.mp4 --transition cross_dissolve

  # 4. Apply the CapCut Viral pack across all internal cuts of a video:
  python3 scripts/apply_transition.py --input video.mp4 -o video_transitions.mp4 --pack capcut_viral

  # 5. Apply the Premiere Pro Classic pack across an edited video:
  python3 scripts/apply_transition.py --input video.mp4 -o video_transitions.mp4 --pack premiere_pro_classic
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from engine.transition_pack import (
    ALL_TRANSITIONS,
    TRANSITION_PACKS,
    apply_two_clip_transition,
    apply_transition_pack_to_video,
    get_transition_info,
)


def print_transition_table():
    print("=" * 86)
    print(" 🎬 PREMIERE PRO & CAPCUT VIRAL TRANSITION ENGINE (55+ TRANSITIONS / 14 PACKS)")
    print("=" * 86)
    
    # 1. Print Packs Summary
    print("\n📦 AVAILABLE TRANSITION PACKS:")
    for pack_id, trans_list in TRANSITION_PACKS.items():
        name_clean = pack_id.replace("_", " ").title()
        print(f"  • {pack_id:<22} ({len(trans_list)} transitions) -> {name_clean}")

    # 2. Print Full Transition Table
    print("\n" + "-" * 86)
    print(f"{'TRANSITION ID':<18} | {'PACK':<20} | {'CATEGORY':<16} | {'SFX':<8} | {'DUR(s)':<6}")
    print("-" * 86)

    for name, info in sorted(ALL_TRANSITIONS.items(), key=lambda x: (x[1].pack, x[0])):
        print(f"{info.name:<18} | {info.pack:<20} | {info.category:<16} | {info.sfx_type:<8} | {info.default_duration:<6.2f}")

    print("-" * 86)
    print("💡 All transitions automatically synthesize frame-accurate 48kHz spatial SFX:")
    print("   (whoosh, boom/808, optical flash, glitch burst, impact thud, ambient riser)\n")


def main():
    parser = argparse.ArgumentParser(
        description="Apply CapCut & Premiere Pro transitions with synchronized audio SFX to video clips."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available CapCut and Premiere Pro transitions and packs.",
    )

    # 2-clip mode
    parser.add_argument("--clip-a", type=Path, help="First video clip (outgoing)")
    parser.add_argument("--clip-b", type=Path, help="Second video clip (incoming)")

    # Single-video cut transition mode
    parser.add_argument("--input", "-i", type=Path, help="Single video file to apply transitions across cuts")
    parser.add_argument("--pack", type=str, default="capcut_viral", choices=list(TRANSITION_PACKS.keys()),
                        help="Transition pack to apply across the video cuts (default: capcut_viral)")
    parser.add_argument("--cuts", type=str, help="Comma-separated cut timestamps in seconds (e.g. 3.2,7.5,12.0). If omitted, auto-detected.")

    # Output & configuration
    parser.add_argument("-o", "--output", type=Path, help="Output destination video file")
    parser.add_argument("--transition", "-t", type=str, default="whip_left",
                        help="Specific transition name (e.g. whip_left, punch_zoom, cross_dissolve, rgb_glitch)")
    parser.add_argument("--duration", type=float, help="Transition duration in seconds (overrides default)")
    parser.add_argument("--no-sfx", action="store_true", help="Disable synchronized transition sound effects")

    args = parser.parse_args()

    if args.list:
        print_transition_table()
        sys.exit(0)

    # Mode 1: 2-clip transition
    if args.clip_a and args.clip_b:
        if not args.output:
            print("❌ Error: --output (-o) is required when joining two clips.")
            sys.exit(1)
        if not args.clip_a.exists():
            print(f"❌ Error: Clip A not found: {args.clip_a}")
            sys.exit(1)
        if not args.clip_b.exists():
            print(f"❌ Error: Clip B not found: {args.clip_b}")
            sys.exit(1)

        t_info = get_transition_info(args.transition)
        if not t_info:
            print(f"⚠ Unknown transition '{args.transition}', falling back to 'whip_left'.")

        print(f"🎬 Merging:\n  Clip A: {args.clip_a}\n  Clip B: {args.clip_b}")
        print(f"  Transition: {args.transition} ({t_info.display_name if t_info else 'Custom'})")
        print(f"  Duration:   {args.duration or (t_info.default_duration if t_info else 0.25):.2f}s")
        print(f"  SFX:        {'Disabled' if args.no_sfx else t_info.sfx_type if t_info else 'whoosh'}")

        out = apply_two_clip_transition(
            clip_a=args.clip_a,
            clip_b=args.clip_b,
            output_path=args.output,
            transition_name=args.transition,
            duration_sec=args.duration,
            with_sfx=not args.no_sfx,
        )
        print(f"✅ Success! Saved to: {out}")
        sys.exit(0)

    # Mode 2: Single video cut transition pack
    if args.input:
        if not args.output:
            out_stem = args.input.stem + f"_trans_{args.pack}"
            args.output = args.input.parent / f"{out_stem}.mp4"

        if not args.input.exists():
            print(f"❌ Error: Input video not found: {args.input}")
            sys.exit(1)

        cut_ts = None
        if args.cuts:
            try:
                cut_ts = [float(x.strip()) for x in args.cuts.split(",") if x.strip()]
            except ValueError:
                print("❌ Error: --cuts must be a comma-separated list of numbers (e.g. 2.5,5.1,9.8)")
                sys.exit(1)

        print(f"🎬 Processing Video: {args.input}")
        print(f"  Transition Pack: {args.pack}")
        print(f"  SFX:             {'Disabled' if args.no_sfx else 'Enabled (Synchronized 48kHz)'}")

        out = apply_transition_pack_to_video(
            input_path=args.input,
            output_path=args.output,
            pack_name=args.pack,
            cut_timestamps=cut_ts,
            with_sfx=not args.no_sfx,
        )
        print(f"✅ Success! Saved to: {out}")
        sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
