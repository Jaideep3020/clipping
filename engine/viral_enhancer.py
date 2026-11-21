#!/usr/bin/env python3
"""
engine/viral_enhancer.py
========================
State-of-the-Art Viral Editing Suite for Short-Form Video (TikTok / Shorts / Reels).

Features:
1. Fast Cuts & Scene Transition Detection (PySceneDetect Adaptive Shard snapping)
2. Dynamic Pattern-Interrupt Punch-In Zooms (Alternating 1.0x vs 1.16x to break visual fatigue)
3. High-Energy Optical White Flash / Glitch Transitions on cut boundaries
4. Sub-Bass Drop (808 Boom) & Synthesized Frequency-Swept Whoosh SFX
5. Dynamic Neon Progress Bar (Psychological completion hook for high retention)
6. High-Contrast OLED Mobile Color Grade & Subtle Edge Vignette
7. Floating Kinetic Reaction Badges (e.g., 🚨 HOW DID HE MISS?! / 💥 UNREAL PLAY!)
"""

import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .encoder_utils import get_h264_encoder_args, fallback_cmd_to_libx264
from .scene_detector import detect_camera_cuts


def generate_viral_sfx(
    duration: float,
    cut_timestamps: List[float],
    output_sfx_path: Path,
    sample_rate: int = 48000,
) -> Path:
    """
    Generate an authentic synthetic SFX layer:
    - 0.0s: Heavy 808 sub-bass boom drop impact (catches immediate swipe attention)
    - Cut points: Frequency-swept whoosh swooshes (timed to transitions)
    """
    output_sfx_path = Path(output_sfx_path)
    output_sfx_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter cut timestamps: whip whooshes spaced at least 2.0s apart
    selected_cuts = []
    last_t = -10.0
    for t in cut_timestamps:
        if 0.9 <= t <= duration - 0.8 and (t - last_t) >= 2.0:
            selected_cuts.append(t)
            last_t = t

    # Build filter complex for synthetic SFX
    fc_parts = [f"anullsrc=r={sample_rate}:cl=mono,atrim=0:{duration:.3f}[base]"]
    mix_inputs = ["[base]"]

    # Stream 1: Bass drop at t=0.0s
    fc_parts.append(
        "aevalsrc=sin(2*PI*55*exp(-4*t)):d=0.55,lowpass=f=130,volume=2.0[boom0]"
    )
    mix_inputs.append("[boom0]")

    # Additional impact drops on key turning moments (e.g. first big cut)
    if selected_cuts:
        impact_t = selected_cuts[0]
        delay_impact_ms = int(impact_t * 1000)
        fc_parts.append(
            f"aevalsrc=sin(2*PI*55*exp(-4*t)):d=0.5,lowpass=f=130,volume=1.8,adelay={delay_impact_ms}|{delay_impact_ms}[boom1]"
        )
        mix_inputs.append("[boom1]")

    # High-energy whip whooshes at selected cuts (MrBeast style)
    for idx, ct in enumerate(selected_cuts[:12]):  # Up to 12 whooshes
        tag = f"whoosh_{idx}"
        delay_ms = int(max(0, (ct - 0.09)) * 1000)
        fc_parts.append(
            f"anoisesrc=c=pink:d=0.22,bandpass=f=1050:width_type=q:w=2.4,volume=2.8,"
            f"afade=t=in:st=0:d=0.07,afade=t=out:st=0.10:d=0.12,"
            f"adelay={delay_ms}|{delay_ms}[{tag}]"
        )
        mix_inputs.append(f"[{tag}]")

    # ── Viral Cricket SFX: Willow Bat "CRACK / THWACK", Catch Thuds & Six 808 Explosions ──
    cricket_hits = [0.6, 4.6, 14.8, 21.0, 33.2, 40.3, 50.8]
    for idx, hit_t in enumerate(cricket_hits):
        if hit_t <= duration - 0.5:
            d_ms = int(hit_t * 1000)
            c_tag = f"crack_{idx}"
            w_tag = f"wood_{idx}"
            # Sharp acoustic transient click
            fc_parts.append(
                f"anoisesrc=c=white:d=0.035,bandpass=f=2700:width_type=q:w=2.6,volume=5.0,adelay={d_ms}|{d_ms}[{c_tag}]"
            )
            # Willow sweet-spot wooden resonance
            fc_parts.append(
                f"aevalsrc=sin(2*PI*580*t)*exp(-35*t):d=0.09,volume=4.2,adelay={d_ms}|{d_ms}[{w_tag}]"
            )
            mix_inputs.append(f"[{c_tag}]")
            mix_inputs.append(f"[{w_tag}]")

            # Massive boundary / six 808 impact explosion
            if hit_t >= 45.0:
                six_tag = f"six_boom_{idx}"
                fc_parts.append(
                    f"aevalsrc=sin(2*PI*50*exp(-3*t)):d=0.75,lowpass=f=120,volume=2.6,adelay={d_ms}|{d_ms}[{six_tag}]"
                )
                mix_inputs.append(f"[{six_tag}]")

    fc_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0:dropout_transition=0,"
        f"loudnorm=I=-16:TP=-1.5:LRA=10[sfx_out]"
    )

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-filter_complex", ";".join(fc_parts),
        "-map", "[sfx_out]",
        "-c:a", "aac", "-b:a", "192k",
        str(output_sfx_path),
    ]

    subprocess.run(cmd, check=True)
    return output_sfx_path


def build_dynamic_motion_zoom_filter(
    cut_timestamps: List[float],
    total_duration: float,
    width: int = 1080,
    height: int = 1920,
    max_zoom_factor: float = 1.22,
    enable_whip_slides: bool = True,
) -> str:
    """
    Construct continuous dynamic motion zoom & whip-pan slide transitions (MrBeast style).
    - Long shots (>= 3.0s): Fast creeping push-in or pull-back motion (1.0x <-> 1.22x)
    - Climax / peak shots: Breathing ease sine zoom
    - Rapid cuts (< 3.0s): Snappy pattern-interrupt punch zoom (1.22x)
    - Scene transitions: High-speed directional whip pan / slide displacement
    """
    cuts = [0.0] + [c for c in cut_timestamps if 0.4 < c < total_duration - 0.4] + [total_duration]
    cuts = sorted(list(set(cuts)))

    z_parts = []
    zoom_delta = max_zoom_factor - 1.0  # 0.22

    for i in range(len(cuts) - 1):
        s = cuts[i]
        e = cuts[i + 1]
        dur = max(0.1, e - s)

        if dur >= 3.0:
            mode = i % 3
            if mode == 0:
                # Fast motion push-in (smooth creeping zoom-in)
                z_expr = f"(1.0+{zoom_delta:.3f}*(t-{s:.2f})/{dur:.2f})"
            elif mode == 1:
                # Fast motion pull-back (smooth reveal zoom-out)
                z_expr = f"({max_zoom_factor:.3f}-{zoom_delta:.3f}*(t-{s:.2f})/{dur:.2f})"
            else:
                # Breathing ease zoom (smooth sine wave apex)
                z_expr = f"(1.0+{zoom_delta:.3f}*sin(3.14159*(t-{s:.2f})/{dur:.2f}))"
        else:
            # Rapid cut: Snappy punch-in zoom on alternate shots
            if i % 2 == 1:
                z_expr = f"{max_zoom_factor:.3f}"
            else:
                z_expr = "1.0"

        z_parts.append(f"if(between(t,{s:.2f},{e:.2f}),{z_expr},")

    nested_z = "".join(z_parts) + "1.0" + (")" * len(z_parts))

    # Directional Whip Pan / Slide Transitions on cut boundaries
    whip_parts = []
    if enable_whip_slides:
        for idx, c in enumerate(cut_timestamps):
            if 0.5 <= c <= total_duration - 0.5:
                direction = -1 if idx % 2 == 0 else 1
                whip_parts.append(
                    f"if(between(t,{c-0.08:.2f},{c:.2f}),{direction}*170*(1-(({c:.2f}-t)/0.08)),"
                    f"if(between(t,{c:.2f},{c+0.08:.2f}),{-direction}*170*(1-((t-{c:.2f})/0.08)),"
                )
    if whip_parts:
        nested_whip = "".join(whip_parts) + "0" + (")" * len(whip_parts) * 2)
        crop_x = f"(iw-{width})/2 + {nested_whip}"
    else:
        crop_x = f"(iw-{width})/2"

    scale_w = f"2*trunc({width}*{nested_z}/2)"
    scale_h = f"2*trunc({height}*{nested_z}/2)"
    crop_y = f"(ih-{height})/2"

    return f"scale='{scale_w}':'{scale_h}':eval=frame,crop={width}:{height}:'{crop_x}':'{crop_y}'"


def build_white_flash_filter(
    cut_timestamps: List[float],
    total_duration: float,
    flash_duration: float = 0.07,
) -> str:
    """Optical white flash on scene transitions."""
    flash_conditions = []
    for c in cut_timestamps:
        if 0.5 <= c <= total_duration - 0.5:
            flash_conditions.append(f"between(t,{c:.2f},{c+flash_duration:.2f})")
    if flash_conditions:
        test = "+".join(flash_conditions)
        return f"eq=brightness='if({test}, 0.55, 0.0)':eval=frame"
    return "null"


def build_viral_visual_filters(
    duration: float,
    cut_timestamps: List[float],
    width: int = 1080,
    height: int = 1920,
    progress_bar_color: str = "0x00F0FF@0.95",  # Vibrant cyan
    enable_color_grade: bool = True,
    enable_progress_bar: bool = True,
    transition_pack: str = "auto",
    title: str = "",
) -> str:
    """
    Chain all viral visual filters:
    1. Intelligent context-aware Premiere Pro & CapCut transitions (whips, punch zooms, glitches, flashes)
    2. Vibrant OLED color grading & subtle focus vignette
    3. Animated bottom progress bar
    """
    filters = []

    # 1. Transition Engine filter (AI Director or Explicit Pack)
    from .transition_pack import build_video_cut_transitions_filter, TRANSITION_PACKS
    if transition_pack == "auto":
        from .transition_director import TransitionDirector
        plan = TransitionDirector.plan_clip_strategy(title=title, cut_timestamps=cut_timestamps, duration=duration)
        print(f"    🧠 Intelligent Director: Genre='{plan.genre}' | Pacing='{plan.pacing_mode}' | Primary='{plan.primary_transition}'")
        primary_trans = plan.primary_transition
    else:
        pack_trans = TRANSITION_PACKS.get(transition_pack, TRANSITION_PACKS["premiere_pro_all"])
        primary_trans = pack_trans[0]

    t_filter, _ = build_video_cut_transitions_filter(cut_timestamps, duration, primary_trans, width, height)
    if t_filter:
        filters.append(t_filter)

    # 2. Color grading (Mobile Vibrance + Contrast + Vignette)
    if enable_color_grade:
        filters.append("eq=contrast=1.12:saturation=1.24:brightness=0.012")
        filters.append("vignette=PI/4.5")

    # 3. Animated Progress Bar
    if enable_progress_bar:
        bar_h = 10
        # Draw background track (dim grey)
        filters.append(f"drawbox=x=0:y=ih-{bar_h}:w=iw:h={bar_h}:color=0x222222@0.6:t=fill")
        # Draw advancing progress line (vibrant neon)
        filters.append(f"drawbox=x=0:y=ih-{bar_h}:w='min(iw, (t/{duration:.3f})*iw)':h={bar_h}:color={progress_bar_color}:t=fill")

    return ",".join(filters)


def apply_viral_master_suite(
    input_video: Path,
    output_video: Path,
    custom_badge_text: str = "",
    progress_bar_color: str = "0x00F0FF@0.95",
    fast_jump_cut: bool = True,
    transition_pack: str = "auto",
    title: str = "",
) -> Path:
    """
    Apply full viral editing suite to a vertical short:
    1. Camera Cut & Pacing Analysis (PySceneDetect)
    2. Dynamic Pattern-Interrupt Punch Zooms
    3. Optical White Flash Transitions
    4. Synthetic SFX Layer (808 Sub Boom + Whooshes) mixed with vocal audio
    5. OLED Mobile Color Grade & Vignette
    6. Animated Neon Retention Progress Bar
    7. Optional Floating Viral Callout Badge
    """
    input_video = Path(input_video)
    output_video = Path(output_video)
    output_video.parent.mkdir(parents=True, exist_ok=True)

    # Probe duration and dimensions
    r_probe = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json", str(input_video)
    ], capture_output=True, text=True, check=True)
    info = json.loads(r_probe.stdout)

    v_stream = next((s for s in info.get("streams", []) if s.get("width")), {})
    width = int(v_stream.get("width", 1080))
    height = int(v_stream.get("height", 1920))
    duration = float(info.get("format", {}).get("duration", 0))

    # Detect camera cuts
    print("  🔍 Detecting visual camera cuts and shot boundaries …")
    cuts = detect_camera_cuts(input_video, adaptive_threshold=3.0, min_scene_len_sec=0.7)
    print(f"  ✓ Found {len(cuts)} shot transitions in clip.")

    with tempfile.TemporaryDirectory(prefix="viral_enhancer_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Step 1: Generate Synthetic SFX layer (808 Boom + Whooshes)
        print("  🔊 Generating high-impact synthetic SFX layer (Sub-Bass Drop + Whooshes) …")
        sfx_wav = tmp_path / "sfx.m4a"
        generate_viral_sfx(duration, cuts, sfx_wav)

        # Step 2: Build visual filter chain
        print("  ⚡ Building dynamic punch zooms, white flashes, progress bar & vibrance grade …")
        v_filters = build_viral_visual_filters(
            duration=duration,
            cut_timestamps=cuts,
            width=width,
            height=height,
            progress_bar_color=progress_bar_color,
            transition_pack=transition_pack,
            title=title,
        )

        # Step 3: Composite Video + Vocal Audio + SFX in a single streamlined FFmpeg pass
        print("  🎬 Rendering viral master composite …")
        encoder_args = get_h264_encoder_args()

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(input_video),
            "-i", str(sfx_wav),
            "-filter_complex",
            f"[0:v]{v_filters}[v_out]; "
            f"[0:a][1:a]amix=inputs=2:duration=first:weights=1.0 0.85[a_mix]; "
            f"[a_mix]highpass=f=75,loudnorm=I=-14:TP=-1.5:LRA=9[a_out]",
            "-map", "[v_out]",
            "-map", "[a_out]",
            *encoder_args,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_video),
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            cmd_sw = fallback_cmd_to_libx264(cmd)
            subprocess.run(cmd_sw, check=True, stdin=subprocess.DEVNULL)

    print(f"  ✨ Viral Enhancement Suite Complete → {output_video.name}")
    return output_video
