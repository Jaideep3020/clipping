#!/usr/bin/env python3
"""
engine/viral_editor.py
======================
Comprehensive Viral Editing Engine for Short-Form Video (TikTok / Shorts / Reels).

Features:
1. Top Hook Headline Banner:
   - High-contrast rounded pill badge at the top of the video
   - Displays for the critical 0-4 second swipe window (or full clip)
2. Framing Reframer (Aspect Ratio):
   - Center Crop (9:16 1080x1920)
   - Blurred Background Pad ('blur_bg'): Keeps 16:9 intact in center, blurred background fills 9:16
3. Mobile Vocal Punch Audio:
   - Highpass 80Hz + EBU R128 loudness normalization targeted to -14 LUFS
4. One-Click Viral Assembler:
   - Combines framing, hook banner, word-by-word dynamic subtitles, and punchy audio
"""

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .encoder_utils import get_h264_encoder_args, fallback_cmd_to_libx264

from .viral_subtitles import burn_viral_subtitles, _get_system_font


# ─────────────────────────────────────────────────────────────────────────────
# 1. Top Hook Headline Banner Generator
# ─────────────────────────────────────────────────────────────────────────────

def render_hook_banner_image(
    width: int,
    height: int,
    headline: str,
    badge_prefix: str = "🔥",
    banner_color: Tuple[int, int, int, int] = (255, 235, 59, 255),  # Yellow
    bg_color: Tuple[int, int, int, int] = (15, 15, 25, 220),         # Dark Glass
) -> Image.Image:
    """Render a transparent 1080x1920 frame containing the top hook banner."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_path = _get_system_font("Impact")
    font = ImageFont.truetype(font_path, 48)
    clean_text = f"{badge_prefix} {headline.upper().strip()}"

    # Calculate text dimensions
    bbox = font.getbbox(clean_text)
    t_w = bbox[2] - bbox[0]
    t_h = bbox[3] - bbox[1]

    # Position at top 10%
    y = int(height * 0.10)
    pad_x, pad_y = 36, 18
    box_w = min(width - 60, t_w + pad_x * 2)
    start_x = (width - box_w) // 2

    # Draw rounded pill badge
    pill_rect = [start_x, y, start_x + box_w, y + t_h + pad_y * 2]
    draw.rounded_rectangle(pill_rect, radius=24, fill=bg_color, outline=(0, 212, 255, 180), width=3)

    # Draw text centered in pill
    text_x = start_x + (box_w - t_w) // 2
    text_y = y + pad_y
    draw.text(
        (text_x, text_y),
        clean_text,
        font=font,
        fill=banner_color,
        stroke_width=3,
        stroke_fill=(0, 0, 0, 255),
    )

    return img


def add_hook_banner_to_video(
    video_path: Path,
    headline: str,
    output_path: Path,
    duration_sec: float = 4.0,  # Display during the first 4 seconds
) -> Path:
    """Burn the top hook headline banner onto the video."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Probe resolution
    r = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "json", str(video_path)
    ], capture_output=True, text=True)
    stream = json.loads(r.stdout).get("streams", [{}])[0]
    width = int(stream.get("width", 1080))
    height = int(stream.get("height", 1920))

    banner_img = render_hook_banner_image(width, height, headline)

    with tempfile.TemporaryDirectory(prefix="hook_banner_") as tmp_dir:
        banner_png = Path(tmp_dir) / "banner.png"
        banner_img.save(banner_png)

        # Overlay with enable='between(t, 0, duration_sec)'
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_path),
            "-i", str(banner_png),
            "-filter_complex", f"[0:v][1:v]overlay=0:0:enable='between(t,0,{duration_sec})'",
        ] + get_h264_encoder_args() + [
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
        r2 = subprocess.run(cmd, capture_output=True, text=True)
        if r2.returncode != 0:
            cmd_sw = fallback_cmd_to_libx264(cmd)
            subprocess.run(cmd_sw, check=True)

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# 2. Reframing: Center Crop vs. Blurred Background Pad
# ─────────────────────────────────────────────────────────────────────────────

def reframe_video_9_16(
    input_video: Path,
    output_video: Path,
    mode: str = "blur_bg",  # 'blur_bg' or 'center_crop'
    start_sec: Optional[float] = None,
    duration_sec: Optional[float] = None,
) -> Path:
    """
    Convert video to vertical 9:16 (1080x1920).
    - 'blur_bg': Keeps 16:9 intact in center, blurred background fills 9:16 (Standard for podcasts/gaming)
    - 'center_crop': Crops center 9:16 portion
    """
    output_video = Path(output_video)
    output_video.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if start_sec is not None:
        cmd += ["-ss", str(start_sec)]
    cmd += ["-i", str(input_video)]
    if duration_sec is not None:
        cmd += ["-t", str(duration_sec)]

    if mode == "blur_bg":
        vf = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg]; "
            "[0:v]scale=1080:-2[fg]; "
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        cmd += ["-filter_complex", vf]
    else:  # 'center_crop'
        vf = "crop=ih*9/16:ih,scale=1080:1920"
        cmd += ["-vf", vf]

    # Audio & codec
    cmd += get_h264_encoder_args() + [
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-af", "highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=10",  # Punchy mobile vocal audio
        "-movflags", "+faststart",
        str(output_video),
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        cmd_sw = fallback_cmd_to_libx264(cmd)
        subprocess.run(cmd_sw, check=True)

    return output_video


# ─────────────────────────────────────────────────────────────────────────────
# 3. Master Viral Clip Assembler
# ─────────────────────────────────────────────────────────────────────────────

def assemble_viral_clip(
    source_video: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
    hook_title: str = "",
    words: Optional[List[Dict[str, Any]]] = None,
    framing_mode: str = "blur_bg",       # 'blur_bg' | 'center_crop' | 'none'
    caption_style: str = "hormozi",      # 'hormozi' | 'mrbeast' | 'neon' | 'minimal' | 'none'
    add_hook_banner: bool = True,
    hook_banner_duration: float = 4.0,
) -> Path:
    """
    One-stop pipeline to generate a fully edited viral short:
    1. Cut & Reframe to 9:16 with vocal punch audio
    2. Add top Hook Banner (if requested)
    3. Burn dynamic word-by-word karaoke subtitles (if requested)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dur = end_sec - start_sec

    with tempfile.TemporaryDirectory(prefix="viral_assemble_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Step 1: Reframe / Cut
        step1_out = tmp_path / "step1_reframed.mp4"
        if framing_mode in ("blur_bg", "center_crop"):
            reframe_video_9_16(source_video, step1_out, mode=framing_mode, start_sec=start_sec, duration_sec=dur)
        else:
            # Cut without reframing
            cmd_cut = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(start_sec), "-i", str(source_video), "-t", str(dur),
            ] + get_h264_encoder_args() + [
                "-c:a", "aac", "-b:a", "192k",
                "-af", "highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=10",
                "-movflags", "+faststart", str(step1_out)
            ]
            rc = subprocess.run(cmd_cut, capture_output=True, text=True)
            if rc.returncode != 0:
                cmd_sw = fallback_cmd_to_libx264(cmd_cut)
                subprocess.run(cmd_sw, check=True)

        current_stage_vid = step1_out

        # Step 2: Hook Banner
        if add_hook_banner and hook_title.strip():
            step2_out = tmp_path / "step2_banner.mp4"
            add_hook_banner_to_video(current_stage_vid, hook_title, step2_out, duration_sec=hook_banner_duration)
            current_stage_vid = step2_out

        # Step 3: Viral Subtitles
        if caption_style != "none" and words:
            step3_out = tmp_path / "step3_captions.mp4"
            burn_viral_subtitles(
                current_stage_vid,
                words,
                step3_out,
                clip_start=start_sec,
                clip_end=end_sec,
                style_name=caption_style,
            )
            current_stage_vid = step3_out

        # Copy final output
        shutil.copy2(str(current_stage_vid), str(output_path))

    return output_path
