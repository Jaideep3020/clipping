#!/usr/bin/env python3
"""
engine/dynamic_transition_engine.py
===================================
Dynamic Non-Repeating Transition Engine.
Solves the uniform cut limitation by assigning distinct, alternating,
and narrative-aware transitions to each individual cut boundary in the video.
Like a professional human editor, it never uses the same transition twice in a row.

Uses clean additive self-contained mathematical expressions for FFmpeg,
avoiding deep nested if() statements.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class CutTransitionAssignment:
    timestamp: float
    transition_type: str        # 'whip_left', 'whip_right', 'whip_up', 'punch_zoom', 'cross_zoom', 'shake', 'glitch', 'flash'
    duration: float             # Duration of transition in seconds
    sfx_type: str               # 'whoosh', 'boom', 'glitch', 'flash', 'thud'
    intensity: float = 1.0


def plan_dynamic_transition_schedule(
    cut_timestamps: List[float],
    total_duration: float,
    genre: str = "viral_general",
) -> List[CutTransitionAssignment]:
    """
    Plan a dynamic, non-repeating sequence of transitions across all cuts.
    Respects the energy curve:
    - 0-3s (Opening Hook): Punch zoom or high-energy flash + 808
    - Build-up / Story: Alternating whip pans (left/right/up), subtle push zooms
    - Climax / High-Energy Moments: Glitches, camera shakes, rapid cross-zooms
    - Resolution / Outro: Smooth dissolves or gentle whip
    """
    valid_cuts = [c for c in sorted(cut_timestamps) if 0.5 <= c <= total_duration - 0.5]
    if not valid_cuts:
        return []

    # Genre-tailored transition palettes with alternating dynamics
    if genre in ["sports", "cricket"]:
        palette = [
            ("whip_left", 0.18, "whoosh"),
            ("punch_zoom", 0.35, "boom"),
            ("whip_right", 0.18, "whoosh"),
            ("optical_flash", 0.12, "flash"),
            ("earthquake_shake", 0.30, "thud"),
            ("whip_up", 0.18, "whoosh"),
            ("cross_zoom", 0.32, "whoosh"),
            ("optical_flash", 0.12, "flash"),
        ]
    elif genre == "gaming":
        palette = [
            ("glitch_analog", 0.22, "glitch"),
            ("cross_zoom", 0.35, "whoosh"),
            ("earthquake_shake", 0.32, "thud"),
            ("whip_left", 0.18, "whoosh"),
            ("optical_flash", 0.10, "flash"),
            ("punch_zoom", 0.30, "boom"),
            ("whip_right", 0.18, "whoosh"),
            ("glitch_analog", 0.20, "glitch"),
        ]
    elif genre in ["podcast", "solo_talker"]:
        palette = [
            ("punch_zoom", 0.28, "whoosh"),
            ("whip_left", 0.16, "whoosh"),
            ("optical_flash", 0.08, "flash"),
            ("punch_zoom", 0.28, "boom"),
            ("whip_right", 0.16, "whoosh"),
            ("cross_zoom", 0.25, "whoosh"),
        ]
    else:  # High-retention viral general (MrBeast style)
        palette = [
            ("whip_left", 0.18, "whoosh"),
            ("punch_zoom", 0.32, "boom"),
            ("whip_right", 0.18, "whoosh"),
            ("cross_zoom", 0.30, "whoosh"),
            ("optical_flash", 0.10, "flash"),
            ("earthquake_shake", 0.28, "thud"),
            ("whip_up", 0.18, "whoosh"),
            ("glitch_analog", 0.20, "glitch"),
        ]

    schedule: List[CutTransitionAssignment] = []
    prev_type = ""

    for idx, c in enumerate(valid_cuts):
        cand = palette[idx % len(palette)]
        if cand[0] == prev_type:
            cand = palette[(idx + 1) % len(palette)]

        # Climax enhancement: If in the last 25% of video (climax zone), boost intensity
        intensity = 1.25 if c >= total_duration * 0.70 else 1.0

        schedule.append(CutTransitionAssignment(
            timestamp=round(c, 3),
            transition_type=cand[0],
            duration=cand[1],
            sfx_type=cand[2],
            intensity=intensity,
        ))
        prev_type = cand[0]

    return schedule


def build_dynamic_transitions_ffmpeg_filter(
    schedule: List[CutTransitionAssignment],
    total_duration: float,
    width: int = 1080,
    height: int = 1920,
) -> Tuple[str, List[str]]:
    """
    Generate an all-in-one FFmpeg video filter string implementing the planned
    dynamic per-cut transition schedule using additive self-contained expressions.
    """
    if not schedule:
        return "", []

    whip_x_terms = []
    whip_y_terms = []
    zoom_terms = []
    flash_parts = []
    glitch_parts = []
    active_motion_windows = []

    for item in schedule:
        c = item.timestamp
        d = item.duration
        half_d = d / 2.0
        t_type = item.transition_type

        # ── 1. Whip Pans & Slides ──
        if "whip" in t_type or "slide" in t_type:
            active_motion_windows.append(f"between(t,{c-half_d:.2f},{c+half_d:.2f})")
            flash_parts.append(f"between(t,{c:.2f},{c+0.05:.2f})")

            if "left" in t_type:
                disp = 190.0 * item.intensity
                whip_x_terms.append(
                    f"if(between(t,{c-half_d:.2f},{c:.2f}),{-disp:.1f}*(1-(({c:.2f}-t)/{half_d:.2f})),"
                    f"if(between(t,{c:.2f},{c+half_d:.2f}),{disp:.1f}*(1-((t-{c:.2f})/{half_d:.2f})),0))"
                )
            elif "right" in t_type:
                disp = 190.0 * item.intensity
                whip_x_terms.append(
                    f"if(between(t,{c-half_d:.2f},{c:.2f}),{disp:.1f}*(1-(({c:.2f}-t)/{half_d:.2f})),"
                    f"if(between(t,{c:.2f},{c+half_d:.2f}),{-disp:.1f}*(1-((t-{c:.2f})/{half_d:.2f})),0))"
                )
            elif "up" in t_type:
                disp = 240.0 * item.intensity
                whip_y_terms.append(
                    f"if(between(t,{c-half_d:.2f},{c:.2f}),{-disp:.1f}*(1-(({c:.2f}-t)/{half_d:.2f})),"
                    f"if(between(t,{c:.2f},{c+half_d:.2f}),{disp:.1f}*(1-((t-{c:.2f})/{half_d:.2f})),0))"
                )

        # ── 2. Punch Zooms ──
        elif "punch_zoom" in t_type:
            p_up, p_hold, p_back = 0.12, 0.14, 0.16
            delta_z = 0.24 * item.intensity
            zoom_terms.append(
                f"if(between(t,{c:.2f},{c+p_up:.2f}),{delta_z:.3f}*(t-{c:.2f})/{p_up:.2f},"
                f"if(between(t,{c+p_up:.2f},{c+p_up+p_hold:.2f}),{delta_z:.3f},"
                f"if(between(t,{c+p_up+p_hold:.2f},{c+p_up+p_hold+p_back:.2f}),"
                f"{delta_z:.3f}*(1-((t-{c+p_up+p_hold:.2f})/{p_back:.2f})),0)))"
            )
            flash_parts.append(f"between(t,{c:.2f},{c+0.04:.2f})")

        # ── 3. Cross Zooms ──
        elif "cross_zoom" in t_type:
            cz_up, cz_down = 0.14, 0.18
            delta_cz = 0.32 * item.intensity
            zoom_terms.append(
                f"if(between(t,{c-cz_up:.2f},{c:.2f}),{delta_cz:.3f}*(1-({c:.2f}-t)/{cz_up:.2f}),"
                f"if(between(t,{c:.2f},{c+cz_down:.2f}),{delta_cz:.3f}*(1-(t-{c:.2f})/{cz_down:.2f}),0))"
            )
            flash_parts.append(f"between(t,{c:.2f},{c+0.06:.2f})")

        # ── 4. Earthquake Camera Tremor ──
        elif "shake" in t_type or "earthquake" in t_type:
            amp = 36.0 * item.intensity
            whip_x_terms.append(
                f"if(between(t,{c:.2f},{c+0.32:.2f}),{amp:.1f}*sin(70*(t-{c:.2f}))*exp(-8*(t-{c:.2f})),0)"
            )
            whip_y_terms.append(
                f"if(between(t,{c:.2f},{c+0.32:.2f}),{amp*0.75:.1f}*cos(60*(t-{c:.2f}))*exp(-8*(t-{c:.2f})),0)"
            )
            flash_parts.append(f"between(t,{c:.2f},{c+0.06:.2f})")

        # ── 5. Analog Data Glitch ──
        elif "glitch" in t_type:
            glitch_parts.append(f"between(t,{c:.2f},{c+0.18:.2f})")
            flash_parts.append(f"between(t,{c:.2f},{c+0.04:.2f})")

        # ── 6. Optical Flash ──
        elif "flash" in t_type:
            flash_parts.append(f"between(t,{c:.2f},{c+0.12:.2f})")

    # Construct the additive mathematical expressions
    v_filters = []

    # 10% base cushion when whip motions are active to prevent black crop edges
    whip_cushion = f"if({'+'.join(active_motion_windows)}, 0.12, 0.0)" if active_motion_windows else "0.0"

    zoom_sum = " + ".join(zoom_terms) if zoom_terms else "0.0"
    total_scale_expr = f"(1.0 + {zoom_sum} + {whip_cushion})"

    scale_w = f"2*trunc({width}*{total_scale_expr}/2)"
    scale_h = f"2*trunc({height}*{total_scale_expr}/2)"

    # Cropping with additive directional x/y displacement
    disp_x_sum = " + ".join(whip_x_terms) if whip_x_terms else "0"
    crop_x = f"(iw-{width})/2 + ({disp_x_sum})"

    disp_y_sum = " + ".join(whip_y_terms) if whip_y_terms else "0"
    crop_y = f"(ih-{height})/2 + ({disp_y_sum})"

    v_filters.append(f"scale='{scale_w}':'{scale_h}':eval=frame,crop={width}:{height}:'{crop_x}':'{crop_y}'")

    # Add Glitch noise burst if scheduled
    if glitch_parts:
        glitch_test = "+".join(glitch_parts)
        v_filters.append(f"noise=alls=16:allf=t+u:enable='{glitch_test}'")

    # Optical White Flash filter
    if flash_parts:
        flash_test = "+".join(flash_parts)
        v_filters.append(f"eq=brightness='if({flash_test}, 0.52, 0.0)':eval=frame")

    return ",".join(v_filters), flash_parts
