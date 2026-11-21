#!/usr/bin/env python3
"""
engine/viral_subtitles.py
=========================
Dynamic Word-by-Word Viral Subtitle Engine.
Inspired by Alex Hormozi, MrBeast, and OpusClip short-form styling.

Features:
- Word-level active highlighting (active word turns neon yellow/cyan/green)
- High-contrast typography with heavy black stroke and drop shadows
- Safe-zone positioning (bottom 30-38%, avoids TikTok/Shorts UI overlays)
- Preset styles: 'hormozi', 'mrbeast', 'neon', 'minimal'
- Generates a transparent QuickTime RLE overlay (.mov) and composites with FFmpeg
"""

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .encoder_utils import get_h264_encoder_args, fallback_cmd_to_libx264


@dataclass
class SubtitleStyle:
    name: str
    font_path: str
    font_size: int
    text_color: Tuple[int, int, int, int]           # Upcoming / inactive words
    highlight_color: Tuple[int, int, int, int]      # Active spoken word
    stroke_color: Tuple[int, int, int, int]         # Border outline
    stroke_width: int
    y_pos_pct: float                                # Vertical position (0.0 to 1.0)
    uppercase: bool = True
    bg_pill: bool = False
    bg_pill_color: Tuple[int, int, int, int] = (0, 0, 0, 160)


def _get_system_font(preferred: str = "Impact") -> str:
    """Find a clean, bold system font on macOS or Linux."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return "Arial"


# ── Presets ───────────────────────────────────────────────────────────────────

def get_style_preset(preset_name: str = "hormozi") -> SubtitleStyle:
    font_file = _get_system_font()
    p = preset_name.lower().strip()

    if p == "mrbeast":
        return SubtitleStyle(
            name="mrbeast",
            font_path=font_file,
            font_size=68,
            text_color=(255, 255, 255, 255),
            highlight_color=(0, 255, 102, 255),    # Vibrant Beast Green
            stroke_color=(0, 0, 0, 255),
            stroke_width=6,
            y_pos_pct=0.68,
            uppercase=True,
            bg_pill=False,
        )
    elif p == "neon":
        return SubtitleStyle(
            name="neon",
            font_path=font_file,
            font_size=66,
            text_color=(255, 255, 255, 255),
            highlight_color=(0, 240, 255, 255),    # Electric Cyan
            stroke_color=(10, 10, 20, 255),
            stroke_width=6,
            y_pos_pct=0.68,
            uppercase=True,
            bg_pill=False,
        )
    elif p == "minimal":
        return SubtitleStyle(
            name="minimal",
            font_path=font_file,
            font_size=54,
            text_color=(240, 240, 245, 255),
            highlight_color=(255, 220, 40, 255),
            stroke_color=(0, 0, 0, 200),
            stroke_width=3,
            y_pos_pct=0.72,
            uppercase=False,
            bg_pill=True,
            bg_pill_color=(15, 15, 25, 180),
        )
    else:  # 'hormozi' default
        return SubtitleStyle(
            name="hormozi",
            font_path=font_file,
            font_size=72,
            text_color=(255, 255, 255, 255),
            highlight_color=(255, 235, 59, 255),   # Alex Hormozi Neon Yellow
            stroke_color=(0, 0, 0, 255),
            stroke_width=7,
            y_pos_pct=0.68,
            uppercase=True,
            bg_pill=False,
        )


# ── Word Burst Grouping ───────────────────────────────────────────────────────

@dataclass
class WordCue:
    word: str
    start: float
    end: float


@dataclass
class CaptionBurst:
    words: List[WordCue]
    start: float
    end: float


def group_words_into_bursts(
    words: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    words_per_burst: int = 4,
    max_pause_sec: float = 0.5,
) -> List[CaptionBurst]:
    """
    Filter words to the clip window, rebase timestamps to 0,
    and group into short 3-5 word bursts for rapid mobile reading.
    """
    clip_words: List[WordCue] = []
    for w in words:
        w_start = float(w.get("start", 0))
        w_end = float(w.get("end", 0))
        # Keep if within clip
        if w_end > clip_start and w_start < clip_end:
            rebased_start = max(0.0, w_start - clip_start)
            rebased_end = min(clip_end - clip_start, w_end - clip_start)
            clean_word = re.sub(r"[^\w\s\$\%\'\-]", "", w.get("word", "")).strip()
            if clean_word:
                clip_words.append(WordCue(
                    word=clean_word,
                    start=round(rebased_start, 3),
                    end=round(rebased_end, 3),
                ))

    if not clip_words:
        return []

    bursts: List[CaptionBurst] = []
    current_burst: List[WordCue] = []

    for i, w in enumerate(clip_words):
        if not current_burst:
            current_burst.append(w)
            continue

        prev_w = current_burst[-1]
        pause = w.start - prev_w.end

        if len(current_burst) >= words_per_burst or pause > max_pause_sec:
            bursts.append(CaptionBurst(
                words=current_burst,
                start=current_burst[0].start,
                end=current_burst[-1].end,
            ))
            current_burst = [w]
        else:
            current_burst.append(w)

    if current_burst:
        bursts.append(CaptionBurst(
            words=current_burst,
            start=current_burst[0].start,
            end=current_burst[-1].end,
        ))

    return bursts


# ── Subtitle Frame Generator ──────────────────────────────────────────────────

def render_caption_frame(
    width: int,
    height: int,
    burst: Optional[CaptionBurst],
    current_time: float,
    style: SubtitleStyle,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Render a single transparent frame with active word highlight."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if not burst or not burst.words:
        return img

    draw = ImageDraw.Draw(img)
    rendered_words = [w.word.upper() if style.uppercase else w.word for w in burst.words]

    # Calculate word bounding boxes and total burst width
    space_width = font.getbbox(" ")[2] - font.getbbox(" ")[0]
    word_boxes = []
    total_w = 0
    for w in rendered_words:
        bbox = font.getbbox(w)
        w_w = bbox[2] - bbox[0]
        w_h = bbox[3] - bbox[1]
        word_boxes.append((w_w, w_h))
        total_w += w_w

    total_w += space_width * (len(rendered_words) - 1)

    # Center horizontally, position at style.y_pos_pct vertically
    start_x = (width - total_w) // 2
    y = int(height * style.y_pos_pct)

    # Optional Pill Background
    if style.bg_pill:
        pad_x, pad_y = 28, 16
        pill_rect = [
            start_x - pad_x,
            y - pad_y,
            start_x + total_w + pad_x,
            y + max(h for _, h in word_boxes) + pad_y * 2,
        ]
        draw.rounded_rectangle(pill_rect, radius=18, fill=style.bg_pill_color)

    # Render each word
    cur_x = start_x
    for i, w_cue in enumerate(burst.words):
        word_str = rendered_words[i]
        w_w, _ = word_boxes[i]

        # Is this word actively being spoken?
        is_active = (w_cue.start <= current_time <= w_cue.end) or (
            i == len(burst.words) - 1 and current_time >= w_cue.start
        )

        fill_color = style.highlight_color if is_active else style.text_color

        # Subtle shadow
        draw.text(
            (cur_x + 3, y + 4),
            word_str,
            font=font,
            fill=(0, 0, 0, 160),
            stroke_width=style.stroke_width + 1,
            stroke_fill=(0, 0, 0, 160),
        )

        # Main text with outline
        draw.text(
            (cur_x, y),
            word_str,
            font=font,
            fill=fill_color,
            stroke_width=style.stroke_width,
            stroke_fill=style.stroke_color,
        )

        cur_x += w_w + space_width

    return img


# ── Full Viral Subtitle Burning Pipeline ──────────────────────────────────────

def burn_viral_subtitles(
    video_path: Path,
    words: List[Dict[str, Any]],
    output_path: Path,
    clip_start: float = 0.0,
    clip_end: Optional[float] = None,
    style_name: str = "hormozi",
    fps: int = 15,
) -> Path:
    """
    Render dynamic animated viral subtitles and burn them directly onto the video.
    Uses Pillow + QuickTime Animation RLE alpha stream to composite seamlessly with FFmpeg.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Probe source video specs
    r_probe = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json", str(video_path)
    ], capture_output=True, text=True)
    info = json.loads(r_probe.stdout)

    v_stream = next((s for s in info.get("streams", []) if s.get("width")), {})
    width = int(v_stream.get("width", 1080))
    height = int(v_stream.get("height", 1920))
    duration = float(info.get("format", {}).get("duration", 0))

    if clip_end is None:
        clip_end = clip_start + duration

    style = get_style_preset(style_name)
    font = ImageFont.truetype(style.font_path, style.font_size)

    # Group words into bursts
    bursts = group_words_into_bursts(words, clip_start, clip_end)
    if not bursts:
        # No words found to subtitle, just copy original
        shutil.copy2(str(video_path), str(output_path))
        return output_path

    total_frames = int(math.ceil(duration * fps))

    with tempfile.TemporaryDirectory(prefix="viral_subs_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()

        # Render frames
        burst_idx = 0
        for f_i in range(total_frames):
            cur_t = f_i / fps
            active_burst = None

            # Advance to current burst
            while burst_idx < len(bursts) and cur_t > bursts[burst_idx].end:
                burst_idx += 1

            if burst_idx < len(bursts) and bursts[burst_idx].start <= cur_t <= bursts[burst_idx].end + 0.2:
                active_burst = bursts[burst_idx]

            frame_img = render_caption_frame(width, height, active_burst, cur_t, style, font)
            frame_img.save(frames_dir / f"frame_{f_i:05d}.png", "PNG")

        # Compile frames into a transparent QuickTime RLE overlay video
        overlay_mov = tmp_path / "overlay.mov"
        cmd_compile = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%05d.png"),
            "-c:v", "qtrle",
            str(overlay_mov),
        ]
        subprocess.run(cmd_compile, check=True)

        # Composite overlay with source video using FFmpeg
        cmd_merge = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_path),
            "-i", str(overlay_mov),
            "-filter_complex", "[0:v][1:v]overlay=0:0",
        ] + get_h264_encoder_args() + [
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]

        r_merge = subprocess.run(cmd_merge, capture_output=True, text=True)
        if r_merge.returncode != 0:
            cmd_sw = fallback_cmd_to_libx264(cmd_merge)
            subprocess.run(cmd_sw, check=True)

    return output_path
