"""
engine/gta6_clipping.py — GTA 6 & Live Stream Clipping Engine
=============================================================
Specialized gaming engine for Grand Theft Auto VI and multi-hour gaming streams:
- Moment taxonomy and viral scoring (Chases, Heists, Stunts, Wasted, Ragdolls, Glitches)
- Gameplay + Facecam stacked 9:16 vertical layout ([game][cam]vstack)
- Cutscene and story spoiler detection (_SPOILER tagging)
- Music-copyright safety routing (removes radio track to avoid DMCA / Content ID)
- Safe-zone validation for social platforms
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

from .encoder_utils import get_h264_encoder_name, fallback_cmd_to_libx264


@dataclass
class GTA6MomentConfig:
    category: str
    pre_sec: float
    post_sec: float
    max_len: float
    keywords: list[str]
    spoiler: bool = False
    mature: bool = False
    impact_slowmo: bool = False
    description: str = ""


GTA6_MOMENTS: dict[str, GTA6MomentConfig] = {
    "police_chase": GTA6MomentConfig(
        category="police_chase",
        pre_sec=10.0,
        post_sec=20.0,
        max_len=90.0,
        keywords=["chase", "siren", "cops", "police", "stars", "wanted", "escape", "helicopter", "swat"],
        description="Police chase or high-speed escape through Leonida / Vice City"
    ),
    "shootout_heist": GTA6MomentConfig(
        category="shootout_heist",
        pre_sec=8.0,
        post_sec=12.0,
        max_len=60.0,
        keywords=["shootout", "gun", "gunfire", "heist", "robbery", "bank", "armor", "sniper", "rpg"],
        mature=True,
        description="Intense shootout, heist, or weapon combat"
    ),
    "stunt_jump": GTA6MomentConfig(
        category="stunt_jump",
        pre_sec=6.0,
        post_sec=10.0,
        max_len=45.0,
        keywords=["stunt", "jump", "ramp", "crash", "flip", "insane stunt", "speed", "launch"],
        impact_slowmo=True,
        description="Vehicle stunt, massive ramp jump, or high-speed collision"
    ),
    "death_arrest": GTA6MomentConfig(
        category="death_arrest",
        pre_sec=12.0,
        post_sec=5.0,
        max_len=40.0,
        keywords=["wasted", "busted", "died", "arrested", "dead", "game over", "fail"],
        description="Death (Wasted) or Police Arrest (Busted) screen"
    ),
    "ragdoll_glitch": GTA6MomentConfig(
        category="ragdoll_glitch",
        pre_sec=8.0,
        post_sec=10.0,
        max_len=45.0,
        keywords=["glitch", "bug", "physics", "ragdoll", "flying", "broken", "weird", "wtf", "lmao"],
        description="Funny physics glitch, NPC ragdoll accident, or visual bug"
    ),
    "funny_dialogue": GTA6MomentConfig(
        category="funny_dialogue",
        pre_sec=6.0,
        post_sec=10.0,
        max_len=50.0,
        keywords=["funny", "npc", "dialogue", "voiceline", "hilarious", "joke", "radio", "talk show"],
        description="Humorous NPC encounter or satirical radio dialogue"
    ),
    "easter_egg": GTA6MomentConfig(
        category="easter_egg",
        pre_sec=10.0,
        post_sec=15.0,
        max_len=60.0,
        keywords=["easter egg", "secret", "hidden", "mystery", "ufo", "lore", "discovery", "uncovered"],
        description="Secret discovery, Easter egg, or hidden map location"
    ),
    "story_reaction": GTA6MomentConfig(
        category="story_reaction",
        pre_sec=5.0,
        post_sec=15.0,
        max_len=75.0,
        keywords=["ending", "reveal", "jason", "lucia", "betrayal", "plot", "cutscene", "mission passed"],
        spoiler=True,
        description="Major campaign story progression or character revelation"
    ),
    "graphics_showcase": GTA6MomentConfig(
        category="graphics_showcase",
        pre_sec=0.0,
        post_sec=20.0,
        max_len=60.0,
        keywords=["graphics", "vice city", "neon", "sunset", "lighting", "water", "rtx", "ray tracing"],
        description="Vice City visual atmosphere or environmental showcase"
    ),
    "rage_moment": GTA6MomentConfig(
        category="rage_moment",
        pre_sec=8.0,
        post_sec=8.0,
        max_len=40.0,
        keywords=["rage", "scream", "desk slam", "unbelievable", "done", "uninstall", "angry"],
        mature=True,
        description="Streamer rage or dramatic reaction"
    )
}


def classify_gta6_moment(text: str) -> tuple[str, float]:
    """Classify transcript text or chat keywords into a GTA 6 moment category."""
    text_lower = text.lower()
    best_cat = "general_gameplay"
    max_hits = 0

    for cat_name, config in GTA6_MOMENTS.items():
        hits = sum(1 for kw in config.keywords if kw in text_lower)
        if hits > max_hits:
            max_hits = hits
            best_cat = cat_name

    confidence = min(1.0, max_hits / 3.0) if max_hits > 0 else 0.2
    return best_cat, confidence


def gameplay_facecam_stack(
    source_path: str,
    output_path: str,
    facecam_roi: tuple[int, int, int, int] = (1440, 810, 480, 270),
    start_sec: Optional[float] = None,
    duration: Optional[float] = None,
    encoder: str = "auto"
) -> str:
    """
    Render 9:16 stacked vertical layout:
    - Top (1080x1344): Main Gameplay (action cropped & centered)
    - Bottom (1080x576): Streamer Facecam (from ROI)
    Total = 1080 x 1920 (perfect 9:16 vertical format)
    """
    if encoder == "auto":
        encoder = get_h264_encoder_name()

    x, y, w, h = facecam_roi

    # Complex filter:
    # 1. Gameplay: crop center 16:9 to fill 1080:1344 (aspect ratio 4:5ish)
    # 2. Facecam: crop ROI (w:h:x:y), scale to 1080:576 (aspect ratio 15:8)
    # 3. Stack vertically: [game][cam]vstack,setsar=1
    fc = (
        f"[0:v]crop=ih*9/16*1.15:ih:(iw-ih*9/16*1.15)/2:0,scale=1080:1344[game]; "
        f"[0:v]crop={w}:{h}:{x}:{y},scale=1080:576[cam]; "
        f"[game][cam]vstack,setsar=1[v]"
    )

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if start_sec is not None:
        cmd += ["-ss", str(start_sec)]
    cmd += ["-i", source_path]
    if duration is not None:
        cmd += ["-t", str(duration)]

    enc_opts = ["-c:v", encoder]
    if encoder == "libx264":
        enc_opts += ["-preset", "fast", "-crf", "20"]
    elif encoder == "h264_videotoolbox":
        enc_opts += ["-b:v", "6000k"]

    cmd += [
        "-filter_complex", fc,
        "-map", "[v]",
        "-map", "0:a?",
        *enc_opts,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        output_path
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        cmd_sw = fallback_cmd_to_libx264(cmd)
        subprocess.run(cmd_sw, check=True)
    return output_path


def detect_cutscene_spoiler(video_path: str, start_sec: float = 0.0, sample_duration: float = 20.0) -> bool:
    """
    Detect whether a video segment is likely a cinematic cutscene (heavy spoilers):
    Heuristic:
    - Persistent letterbox black bars (cinema 2.39:1 aspect ratio) detected via cropdetect.
    """
    try:
        cmd = [
            "ffmpeg", "-hide_banner", "-ss", str(start_sec), "-t", str(sample_duration),
            "-i", video_path,
            "-vf", "cropdetect=24:16:0",
            "-f", "null", "-"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", res.stderr)
        if not crops:
            return False

        # If detected height is consistently <= 82% of original 1080p (black bars >= 90px top & bottom)
        letterboxed = 0
        for w, h, x, y in crops[-15:]:
            if int(h) <= 880:  # 1080p letterboxed
                letterboxed += 1

        return letterboxed >= 8
    except Exception:
        return False


def render_music_safe_variant(
    video_path: str,
    output_path: str,
    keep_audio_tracks: list[int] = [0],
    encoder: str = "copy"
) -> str:
    """
    Produce a music-safe version of a clip to protect against YouTube Content ID or Twitch DMCA:
    - Drops secondary audio tracks (e.g. in-game radio track)
    - Normalizes voice / SFX audio to -14 LUFS
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Map video track + selected audio track(s)
    maps = ["-map", "0:v:0"]
    for t in keep_audio_tracks:
        maps += ["-map", f"0:a:{t}"]

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", video_path,
        *maps,
        "-c:v", encoder,
        "-c:a", "aac",
        "-af", "highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=11",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path


def format_gta6_clip_filename(
    stem: str,
    rank: int,
    category: str,
    start_sec: float,
    end_sec: float,
    is_spoiler: bool = False,
    is_vertical: bool = False
) -> str:
    """Produce standardized filename according to skill specifications."""
    tag = "_SPOILER" if is_spoiler else ""
    vert = ".v" if is_vertical else ""
    return f"{stem}_{rank:02d}_{category}_{int(start_sec)}-{int(end_sec)}{tag}{vert}.mp4"
