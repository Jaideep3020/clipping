#!/usr/bin/env python3
"""
engine/smart_editor.py
======================
Autonomous AI Video Editor & Dynamic Post-Production Suite.
Mimics a professional human video editor by choreographing:
- Dynamic non-repeating transitions (whips, punch zooms, cross zooms, shakes, glitches, flashes)
- Contextual sound design & SFX layer matched to visual transitions & audio transients
- 2-4s Pattern Interrupts: Audio-synced punch zooms and creeping push-ins on static shots
- Cinematic Color Grading (Teal & Orange, Hyper Vibrant, Warm Golden, Moody Filmic)
- Atmospheric overlays (35mm subtle film grain, chromatic impact fringe)
- 0-3s Opening Hook retention setup with 808 sub-bass impact
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .audio_beat_sync import AudioEnergyProfile, analyze_audio_energy
from .color_grading import get_color_grade_filter, recommend_color_grade_for_genre
from .dynamic_transition_engine import (
    CutTransitionAssignment,
    build_dynamic_transitions_ffmpeg_filter,
    plan_dynamic_transition_schedule,
)
from .encoder_utils import fallback_cmd_to_libx264, get_h264_encoder_args
from .overlay_effects import build_atmospheric_overlay_filter
from .smart_sfx_designer import synthesize_contextual_sfx


@dataclass
class MasterEditorialRecipe:
    genre: str
    duration: float
    transition_schedule: List[CutTransitionAssignment]
    color_grade: str
    enable_grain: bool
    enable_chromatic_fringe: bool
    pattern_interrupt_zooms: List[float]
    sfx_events_count: int
    rationale: str


def build_pattern_interrupt_zoom_filter(
    cuts: List[float],
    duration: float,
    audio_profile: AudioEnergyProfile,
    width: int = 1080,
    height: int = 1920,
    max_zoom: float = 1.16,
) -> str:
    """
    Construct continuous dynamic zooms implementing the 3-Second Rule:
    - Shots >= 3.5s without camera cut receive audio-synced punch-ins or smooth creeping pushes
    - Uses clean additive self-contained expressions (zero deep nesting).
    """
    all_boundaries = sorted(list(set([0.0] + [c for c in cuts if 0.4 < c < duration - 0.4] + [duration])))
    z_terms = []
    zoom_delta = max_zoom - 1.0

    for i in range(len(all_boundaries) - 1):
        s = all_boundaries[i]
        e = all_boundaries[i + 1]
        seg_dur = max(0.1, e - s)

        if seg_dur >= 3.5:
            internal_spikes = [spk for spk in audio_profile.energy_spikes if s + 1.0 <= spk <= e - 1.0]
            if internal_spikes:
                spk = internal_spikes[0]
                z_terms.append(
                    f"if(between(t,{s:.2f},{spk:.2f}),{zoom_delta*0.5:.3f}*(t-{s:.2f})/{max(0.1, spk-s):.2f},"
                    f"if(between(t,{spk:.2f},{e:.2f}),{zoom_delta:.3f},0))"
                )
            else:
                mode = i % 2
                if mode == 0:
                    z_terms.append(f"if(between(t,{s:.2f},{e:.2f}),{zoom_delta:.3f}*(t-{s:.2f})/{seg_dur:.2f},0)")
                else:
                    z_terms.append(f"if(between(t,{s:.2f},{e:.2f}),{zoom_delta:.3f}*(1-((t-{s:.2f})/{seg_dur:.2f})),0)")
        else:
            if i % 2 == 1:
                z_terms.append(f"if(between(t,{s:.2f},{e:.2f}),{zoom_delta:.3f},0)")

    z_sum = " + ".join(z_terms) if z_terms else "0.0"
    total_z_expr = f"(1.0 + {z_sum})"

    scale_w = f"2*trunc({width}*{total_z_expr}/2)"
    scale_h = f"2*trunc({height}*{total_z_expr}/2)"
    crop_x = f"(iw-{width})/2"
    crop_y = f"(ih-{height})/2"

    return f"scale='{scale_w}':'{scale_h}':eval=frame,crop={width}:{height}:'{crop_x}':'{crop_y}'"


def apply_smart_autonomous_edit(
    input_video: Path,
    output_video: Path,
    title: str = "",
    genre: Optional[str] = None,
    color_grade: Optional[str] = None,
    enable_sfx: bool = True,
    enable_overlays: bool = True,
    enable_progress_bar: bool = True,
    progress_bar_color: str = "0x00F0FF@0.95",
) -> Path:
    """
    Execute the entire Autonomous Master Edit pipeline:
    1. Audio Intelligence & RMS analysis
    2. Scene visual boundary extraction
    3. Dynamic non-repeating transition scheduling
    4. Audio-synced pattern interrupt zooms (3-second rule)
    5. Contextual sound design synthesis
    6. Cinematic color grading & atmospheric film texture
    7. High-performance hardware-accelerated encode
    """
    input_video = Path(input_video)
    output_video = Path(output_video)
    output_video.parent.mkdir(parents=True, exist_ok=True)

    if not input_video.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")

    print(f"\n🎬 [Smart Autonomous Editor] Beginning professional edit on {input_video.name} …")

    # ── 1. Probe & Specs ──
    r_probe = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json", str(input_video)
    ], capture_output=True, text=True)
    import json
    info = json.loads(r_probe.stdout)
    v_stream = next((s for s in info.get("streams", []) if s.get("width")), {})
    width = int(v_stream.get("width", 1080))
    height = int(v_stream.get("height", 1920))
    duration = float(info.get("format", {}).get("duration", 30.0))

    # ── 2. Audio Intelligence & Energy Profiling ──
    print("    🔍 Analyzing audio energy, speech peaks & transient onsets …")
    audio_profile = analyze_audio_energy(input_video)
    print(f"       • Mean Energy: {audio_profile.mean_energy:.3f} | Spikes: {len(audio_profile.energy_spikes)} | Onsets: {len(audio_profile.transient_onsets)}")

    # ── 3. Visual Shot Cut Detection ──
    print("    ✂️ Detecting visual shot cut boundaries …")
    from .scene_detector import detect_camera_cuts
    cut_timestamps = detect_camera_cuts(input_video)
    print(f"       • Found {len(cut_timestamps)} natural visual shot cuts.")

    # ── 4. Determine Genre & Narrative Strategy ──
    if not genre:
        from .transition_director import TransitionDirector
        genre = TransitionDirector.detect_genre(title=title)
    print(f"    🧠 Narrative Archetype: {genre.upper()}")

    # ── 5. Plan Dynamic Transition Schedule ──
    transition_schedule = plan_dynamic_transition_schedule(
        cut_timestamps=cut_timestamps,
        total_duration=duration,
        genre=genre,
    )
    print(f"    ✨ Planned {len(transition_schedule)} dynamic non-repeating transitions:")
    for idx, t_item in enumerate(transition_schedule[:6]):
        print(f"       [{idx+1}] t={t_item.timestamp:.2f}s ➔ {t_item.transition_type} ({t_item.sfx_type})")
    if len(transition_schedule) > 6:
        print(f"       ... and {len(transition_schedule) - 6} more alternating transitions.")

    # ── 6. Build Video Filter Graph ──
    vf_list = []

    # A. Dynamic Transitions Filter
    trans_vf, flash_conds = build_dynamic_transitions_ffmpeg_filter(
        schedule=transition_schedule,
        total_duration=duration,
        width=width,
        height=height,
    )
    if trans_vf:
        vf_list.append(trans_vf)

    # B. Pattern Interrupt Zooms (3-Second Rule)
    zoom_vf = build_pattern_interrupt_zoom_filter(
        cuts=cut_timestamps,
        duration=duration,
        audio_profile=audio_profile,
        width=width,
        height=height,
        max_zoom=1.15,
    )
    if zoom_vf:
        vf_list.append(zoom_vf)

    # C. Cinematic Color Grading
    if not color_grade:
        color_grade = recommend_color_grade_for_genre(genre)
    cg_filter = get_color_grade_filter(color_grade)
    print(f"    🎨 Applying Cinematic Color Grade: {color_grade.upper()}")
    vf_list.append(cg_filter)

    # D. Atmospheric Overlays (Subtle 35mm grain + impact chromatic aberration)
    if enable_overlays:
        chromatic_ts = [t.timestamp for t in transition_schedule if t.sfx_type in ["boom", "thud", "glitch"]]
        overlay_vf = build_atmospheric_overlay_filter(
            enable_grain=True,
            enable_chromatic_fringe=True,
            chromatic_moments=chromatic_ts,
        )
        if overlay_vf:
            vf_list.append(overlay_vf)

    # E. Animated Bottom Progress Bar
    if enable_progress_bar:
        bar_h = 10
        vf_list.append(f"drawbox=x=0:y=ih-{bar_h}:w=iw:h={bar_h}:color=0x222222@0.6:t=fill")
        vf_list.append(f"drawbox=x=0:y=ih-{bar_h}:w='min(iw, (t/{duration:.3f})*iw)':h={bar_h}:color={progress_bar_color}:t=fill")

    final_vf = ",".join(vf_list)

    # ── 7. Synthesize Contextual SFX Layer ──
    with tempfile.TemporaryDirectory(prefix="smart_edit_") as tmp_dir:
        tmp_p = Path(tmp_dir)
        sfx_path = tmp_p / "contextual_sfx.aac"

        has_sfx = False
        if enable_sfx:
            print("    🔊 Synthesizing contextual sound design & SFX layer …")
            sfx_res = synthesize_contextual_sfx(
                video_path=input_video,
                output_sfx_path=sfx_path,
                transition_schedule=transition_schedule,
                audio_profile=audio_profile,
                duration=duration,
                genre=genre,
            )
            has_sfx = (sfx_res is not None and sfx_path.exists() and sfx_path.stat().st_size > 0)

        # ── 8. Assemble & Encode ──
        print("    ⚡ Compositing & rendering master edit …")
        encoder_args = get_h264_encoder_args()

        if has_sfx:
            # Mix original video audio with the synthesized SFX layer
            fc = (
                f"[0:v]{final_vf}[v_out]; "
                f"[0:a]volume=1.0[a_orig]; "
                f"[1:a]volume=1.1[a_sfx]; "
                f"[a_orig][a_sfx]amix=inputs=2:normalize=0:dropout_transition=0,"
                f"loudnorm=I=-14:TP=-1.5:LRA=10[a_out]"
            )
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(input_video),
                "-i", str(sfx_path),
                "-filter_complex", fc,
                "-map", "[v_out]",
                "-map", "[a_out]",
            ] + encoder_args + [
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(output_video)
            ]
        else:
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(input_video),
                "-vf", final_vf,
                "-c:a", "aac", "-b:a", "192k",
                "-af", "highpass=f=75,loudnorm=I=-14:TP=-1.5:LRA=10",
            ] + encoder_args + [
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(output_video)
            ]

        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("    ⚠ Primary hardware encode error, falling back to libx264 …")
            cmd_sw = fallback_cmd_to_libx264(cmd)
            r_sw = subprocess.run(cmd_sw, capture_output=True, text=True)
            if r_sw.returncode != 0:
                raise RuntimeError(f"Master render failed: {r_sw.stderr[-800:]}")

    if output_video.exists() and output_video.stat().st_size > 0:
        sz_mb = round(output_video.stat().st_size / 1_048_576, 2)
        print(f"  ✅ [Smart Autonomous Editor] Completed: {output_video.name} ({sz_mb} MB)\n")
        return output_video
    else:
        raise RuntimeError("Output file was not generated or empty.")
