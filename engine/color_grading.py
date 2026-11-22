#!/usr/bin/env python3
"""
engine/color_grading.py
=======================
Cinematic Color Grading Engine for Short-Form Video.
Applies industry-standard Hollywood and viral aesthetic looks programmatically
using native FFmpeg color balance, curves, and contrast filters without
requiring external .cube LUT files.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ColorGradePreset:
    name: str
    display_name: str
    description: str
    ffmpeg_filter: str


# ── Curated Cinematic Presets ─────────────────────────────────────────────────
# Formulated according to professional digital colorist standards:
# - Teal & Orange: Cool cyan/blue shadows + Warm amber/orange highlights with contrast S-curve
# - Hyper Vibrant: Saturated, dynamic contrast pop for Sports and Gaming
# - Warm Golden: Radiant skin tones and soft golden highlights for Podcasts and Talkers
# - Moody Filmic: Muted midtones, crushed blacks, dramatic contrast for storytelling
# - Clean Boost: Crisp, neutral studio look with lifted details and mild vignette

COLOR_GRADE_PRESETS: Dict[str, ColorGradePreset] = {
    "teal_orange": ColorGradePreset(
        name="teal_orange",
        display_name="Blockbuster Teal & Orange",
        description="Hollywood blockbuster viral look: cool cyan shadows, warm amber highlights, rich S-curve.",
        ffmpeg_filter=(
            "colorbalance=bs=0.22:rs=-0.12:gh=-0.05:rh=0.18:bh=-0.14,"
            "curves=all='0/0 0.22/0.15 0.5/0.52 0.78/0.88 1/1',"
            "eq=contrast=1.10:saturation=1.20:brightness=0.01,"
            "vignette=PI/5.5"
        ),
    ),
    "hyper_vibrant": ColorGradePreset(
        name="hyper_vibrant",
        display_name="Hyper Vibrant (Sports & Gaming)",
        description="Ultra-vivid colors, razor-sharp contrast, dynamic punch for fast action.",
        ffmpeg_filter=(
            "eq=contrast=1.14:saturation=1.28:brightness=0.015,"
            "curves=all='0/0 0.2/0.16 0.5/0.5 0.8/0.86 1/1',"
            "colorbalance=rm=0.05:gm=0.02:bm=0.04,"
            "vignette=PI/5.0"
        ),
    ),
    "warm_golden": ColorGradePreset(
        name="warm_golden",
        display_name="Golden Hour (Podcast & Vlogs)",
        description="Radiant, healthy skin tones with golden ambient warmth.",
        ffmpeg_filter=(
            "colorbalance=rs=0.08:gs=0.02:bs=-0.08:rm=0.10:gm=0.04:bm=-0.08:rh=0.12:gh=0.05:bh=-0.10,"
            "eq=contrast=1.08:saturation=1.16:brightness=0.02,"
            "curves=all='0/0 0.25/0.22 0.5/0.52 0.75/0.82 1/1',"
            "vignette=PI/6.0"
        ),
    ),
    "moody_cinematic": ColorGradePreset(
        name="moody_cinematic",
        display_name="Moody Filmic",
        description="Deep shadows, subtle desaturation, cinematic indie film texture.",
        ffmpeg_filter=(
            "colorbalance=bs=0.15:rs=-0.05:bh=-0.08:rh=0.05,"
            "curves=all='0/0 0.3/0.20 0.5/0.48 0.7/0.78 1/1',"
            "eq=contrast=1.16:saturation=1.05:brightness=-0.02,"
            "vignette=PI/4.2"
        ),
    ),
    "clean_boost": ColorGradePreset(
        name="clean_boost",
        display_name="Studio Clean Pop",
        description="Clean high-definition studio clarity with vibrant presence.",
        ffmpeg_filter=(
            "eq=contrast=1.10:saturation=1.18:brightness=0.01,"
            "curves=all='0/0 0.25/0.20 0.5/0.5 0.75/0.82 1/1',"
            "vignette=PI/6.5"
        ),
    ),
}


def get_color_grade_filter(preset_name: str = "teal_orange") -> str:
    """Return the FFmpeg filter string for a given color grade preset."""
    preset = COLOR_GRADE_PRESETS.get(preset_name.lower().strip())
    if not preset:
        preset = COLOR_GRADE_PRESETS["teal_orange"]
    return preset.ffmpeg_filter


def recommend_color_grade_for_genre(genre: str) -> str:
    """
    Intelligently select the best color grading style based on video genre.
    """
    g = genre.lower().strip()
    if g in ["sports", "cricket"]:
        return "hyper_vibrant"
    elif g in ["gaming"]:
        return "teal_orange"
    elif g in ["podcast", "solo_talker", "vlog"]:
        return "warm_golden"
    elif g in ["keynote", "educational"]:
        return "clean_boost"
    else:
        return "teal_orange"
