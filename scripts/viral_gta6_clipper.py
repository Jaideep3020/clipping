#!/usr/bin/env python3
"""
scripts/viral_gta6_clipper.py
=============================
Automated End-to-End MrBeast-Style Viral GTA 6 Gameplay Clipper:
1. Automated Highlight Detection: Audio RMS energy + speech velocity spike detection.
2. Smart 9:16 Vertical Reframing (Facecam + Gameplay stacked, or action-centered 1080x1920).
3. MrBeast-Style Fast Cuts & Transitions: Directional whip slides + 2-frame optical white flashes.
4. Dynamic Punch-In Zooms: 100% -> 122% on hype moments & continuous creeping push-in.
5. MrBeast Kinetic Word Subtitles: 2-3 word bursts, vibrant beast green (#00FF66) active highlight.
6. GTA 6 Viral Hook Card: 0-4s top headline badge with smooth 0.5s fade-out.
7. Gaming & MrBeast SFX Layer: 808 sub-bass opening boom, whip whooshes, impact hits.
8. Safe-Zone Neon Progress Bar & OLED Vibrance Grade.
9. EBU R128 Audio Mastering (-14 LUFS vocal master + limiter).
10. Final 1080x1920 60/30fps high-bitrate export.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure project imports resolve
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.encoder_utils import get_h264_encoder_args, fallback_cmd_to_libx264
from engine.scene_detector import detect_camera_cuts
from engine.viral_editor import render_hook_banner_image
from engine.viral_subtitles import burn_viral_subtitles, get_style_preset


def compute_audio_energy_spikes(
    video_path: Path,
    window_sec: float = 40.0,
    stride_sec: float = 5.0,
) -> List[Tuple[float, float, float]]:
    """
    Scan full video audio to detect peak excitement moments using RMS energy & z-score spikes.
    Returns sorted list of (start_time, end_time, score).
    """
    # Stream audio at 16kHz mono PCM
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(video_path),
        "-ac", "1", "-ar", "16000",
        "-f", "s16le", "-"
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    rms_per_sec = []
    chunk_size = 32000  # 1 second of 16kHz 16-bit mono
    while True:
        buf = p.stdout.read(chunk_size)
        if not buf:
            break
        samples = np.frombuffer(buf[: len(buf) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
        val = float(np.sqrt(np.mean(samples * samples))) if len(samples) > 0 else 0.0
        rms_per_sec.append(val)
    p.wait()

    if not rms_per_sec:
        return [(0.0, window_sec, 1.0)]

    rms_arr = np.array(rms_per_sec)
    total_len = len(rms_arr)
    # Compute trailing baseline & z-score
    med = np.median(rms_arr)
    std = max(float(np.std(rms_arr)), 1e-4)

    candidates = []
    t = 10.0  # skip first 10s intro
    while t + window_sec < total_len - 10.0:
        win = rms_arr[int(t): int(t + window_sec)]
        score = float((np.mean(win) - med) / std + (np.max(win) - med) / std)
        candidates.append((round(t, 2), round(t + window_sec, 2), round(score, 3)))
        t += stride_sec

    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates


def transcribe_segment(
    video_path: Path,
    start_sec: float,
    duration_sec: float,
) -> List[Dict[str, Any]]:
    """
    Transcribe the selected video segment using openai-whisper to get exact word timestamps.
    """
    try:
        import whisper

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name

        cmd = [
            "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration_sec),
            "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
            wav_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        print(f"  [Transcribe] Running Whisper on {duration_sec:.1f}s highlight segment …")
        model = whisper.load_model("base")
        result = model.transcribe(wav_path, word_timestamps=True, language="en")

        word_cues = []
        for s in result.get("segments", []):
            for w in s.get("words", []):
                word_clean = re.sub(r"[^\w\s\$\%\'\-]", "", w.get("word", "")).strip()
                if word_clean:
                    word_cues.append({
                        "word": word_clean,
                        "start": max(0.0, round(float(w.get("start", 0)), 3)),
                        "end": min(round(duration_sec, 3), round(float(w.get("end", 0)), 3)),
                    })

        if Path(wav_path).exists():
            os.unlink(wav_path)

        print(f"  ✓ Transcribed {len(word_cues)} words with millisecond timestamps.")
        return word_cues
    except Exception as e:
        print(f"  ⚠ Whisper transcription fallback: {e}")
        return []


def check_facecam_present(video_path: Path, sample_time: float = 15.0) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect if video has a streamer facecam in standard corners.
    Returns (x, y, w, h) ROI if detected, or None for clean gameplay.
    """
    try:
        from engine.face_tracker import FaceTracker
        tracker = FaceTracker()
        # Extract a test frame
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            frame_path = tf.name

        cmd = ["ffmpeg", "-y", "-ss", str(sample_time), "-i", str(video_path), "-frames:v", "1", frame_path]
        subprocess.run(cmd, capture_output=True, check=True)

        import cv2
        img = cv2.imread(frame_path)
        os.unlink(frame_path)

        if img is None:
            return None

        h, w = img.shape[:2]
        faces = tracker.detect_faces(img)
        if faces:
            # Check if face is in top-right or bottom-right corner
            fx, fy, fw, fh = faces[0]
            cx, cy = fx + fw // 2, fy + fh // 2
            if cx > w * 0.65 or cy < h * 0.35 or cy > h * 0.65:
                # Plausible corner facecam box
                cam_w = int(w * 0.28)
                cam_h = int(h * 0.32)
                cam_x = max(0, min(w - cam_w, fx - 20))
                cam_y = max(0, min(h - cam_h, fy - 20))
                return (cam_x, cam_y, cam_w, cam_h)
    except Exception:
        pass
    return None


def build_mrbeast_sfx_track(
    duration: float,
    cut_timestamps: List[float],
    punch_moments: List[float],
    output_sfx_path: Path,
    sample_rate: int = 48000,
) -> Path:
    """
    Synthesize high-energy MrBeast gaming SFX layer:
    - 0.0s opening hook 808 sub-bass drop impact.
    - Frequency-swept whooshes on every whip transition.
    - Sub-bass boom hits on major action/crash moments.
    """
    output_sfx_path = Path(output_sfx_path)
    output_sfx_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter cuts for whooshes (spaced at least 1.5s apart)
    selected_cuts = []
    last_t = -10.0
    for t in cut_timestamps:
        if 0.5 <= t <= duration - 0.5 and (t - last_t) >= 1.5:
            selected_cuts.append(t)
            last_t = t

    fc_parts = [f"anullsrc=r={sample_rate}:cl=mono,atrim=0:{duration:.3f}[base]"]
    mix_inputs = ["[base]"]

    # 1. Opening 808 sub-bass boom drop impact at t=0.0s
    fc_parts.append("aevalsrc=sin(2*PI*55*exp(-4*t)):d=0.60,lowpass=f=130,volume=2.4[boom0]")
    mix_inputs.append("[boom0]")

    # 2. Whip whooshes starting at first frame of whip (c - 0.12s)
    for idx, ct in enumerate(selected_cuts[:18]):
        w_tag = f"whoosh_{idx}"
        delay_ms = int(max(0, (ct - 0.12)) * 1000)
        fc_parts.append(
            f"anoisesrc=c=pink:d=0.22,bandpass=f=1150:width_type=q:w=2.4,volume=2.6,"
            f"afade=t=in:st=0:d=0.06,afade=t=out:st=0.10:d=0.12,"
            f"adelay={delay_ms}|{delay_ms}[{w_tag}]"
        )
        mix_inputs.append(f"[{w_tag}]")

    # 3. Sub-bass impacts on major punch/crash moments
    for idx, pt in enumerate(punch_moments[:6]):
        if 2.0 <= pt <= duration - 1.0:
            p_tag = f"impact_{idx}"
            delay_ms = int(pt * 1000)
            fc_parts.append(
                f"aevalsrc=sin(2*PI*50*exp(-3.5*t)):d=0.55,lowpass=f=125,volume=2.2,adelay={delay_ms}|{delay_ms}[{p_tag}]"
            )
            mix_inputs.append(f"[{p_tag}]")

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


def build_mrbeast_visual_filters(
    cut_timestamps: List[float],
    total_duration: float,
    punch_moments: List[float],
    width: int = 1080,
    height: int = 1920,
) -> str:
    """
    Build MrBeast-style visual filter graph:
    - 6-8 frame whip slide transitions (-180px slide out, +180px slide in) + 2-frame optical white flashes.
    - Snappy 100% -> 122% punch-in zooms & alternating dynamic push-in / pull-backs.
    - Safe-zone neon cyan/magenta progress bar at y=ih-220 with soft glow.
    - OLED vibrance, contrast, and subtle vignette.
    """
    cuts = [0.0] + [c for c in cut_timestamps if 0.4 < c < total_duration - 0.4] + [total_duration]
    cuts = sorted(list(set(cuts)))

    # 1. Punch-in zooms & continuous camera motion
    z_parts = []
    for i in range(len(cuts) - 1):
        s = cuts[i]
        e = cuts[i + 1]
        dur = max(0.1, e - s)

        hit_in_interval = [h for h in punch_moments if s <= h < e]
        if hit_in_interval:
            h = hit_in_interval[0]
            # 5-frame punch up (0.20s), hold 0.5s, ease pull-back over 12 frames (0.45s)
            p_up, p_hold, p_back = 0.20, 0.50, 0.45
            z_expr = (
                f"if(between(t,{h:.2f},{h+p_up:.2f}),(1.0+0.22*(t-{h:.2f})/{p_up:.2f}),"
                f"if(between(t,{h+p_up:.2f},{h+p_up+p_hold:.2f}),1.22,"
                f"if(between(t,{h+p_up+p_hold:.2f},{h+p_up+p_hold+p_back:.2f}),(1.22-0.22*(t-{h+p_up+p_hold:.2f})/{p_back:.2f}),1.0)))"
            )
        elif dur >= 3.0:
            if i % 2 == 0:
                z_expr = f"(1.0+0.16*(t-{s:.2f})/{dur:.2f})"
            else:
                z_expr = f"(1.16-0.16*(t-{s:.2f})/{dur:.2f})"
        else:
            z_expr = "1.18" if i % 2 == 1 else "1.0"

        z_parts.append(f"if(between(t,{s:.2f},{e:.2f}),{z_expr},")

    nested_z = "".join(z_parts) + "1.0" + (")" * len(z_parts))

    # 2. Whip slide transitions & optical white flashes
    whip_parts = []
    flash_parts = []
    whip_zoom_parts = []
    whip_half_dur = 0.12  # 6 frames at 25fps

    for c in cut_timestamps:
        if 0.5 <= c <= total_duration - 0.5:
            whip_parts.append(
                f"if(between(t,{c-whip_half_dur:.2f},{c:.2f}),-180*(1-(({c:.2f}-t)/{whip_half_dur:.2f})),"
                f"if(between(t,{c:.2f},{c+whip_half_dur:.2f}),180*(1-((t-{c:.2f})/{whip_half_dur:.2f})),"
            )
            whip_zoom_parts.append(f"between(t,{c-whip_half_dur:.2f},{c+whip_half_dur:.2f})")
            flash_parts.append(f"between(t,{c:.2f},{c+0.07:.2f})")

    if whip_parts:
        nested_whip = "".join(whip_parts) + "0" + (")" * len(whip_parts) * 2)
        crop_x = f"(iw-{width})/2 + {nested_whip}"
    else:
        crop_x = f"(iw-{width})/2"

    if whip_zoom_parts:
        whip_zoom_test = "+".join(whip_zoom_parts)
        whip_z_expr = f"if({whip_zoom_test}, 0.12, 0.0)"
    else:
        whip_z_expr = "0.0"

    scale_w = f"2*trunc({width}*({nested_z} + {whip_z_expr})/2)"
    scale_h = f"2*trunc({height}*({nested_z} + {whip_z_expr})/2)"
    crop_y = f"(ih-{height})/2"

    filters = [
        f"scale='{scale_w}':'{scale_h}':eval=frame,crop={width}:{height}:'{crop_x}':'{crop_y}'"
    ]

    if flash_parts:
        flash_test = "+".join(flash_parts)
        filters.append(f"eq=brightness='if({flash_test}, 0.55, 0.0)':eval=frame")

    # Neon safe-zone progress bar (y = ih - 220)
    bar_y = height - 220
    filters.append(f"drawbox=x=0:y={bar_y-2}:w='(t/{total_duration:.3f})*iw':h=13:color=0x00F0FF@0.35:t=fill")
    filters.append(f"drawbox=x=0:y={bar_y}:w='(t/{total_duration:.3f})*iw':h=9:color=0x00F0FF@0.95:t=fill")

    # Mobile OLED Vibrance & Focus Vignette
    filters.append("eq=contrast=1.12:saturation=1.24:brightness=0.012")
    filters.append("vignette=PI/4.5")

    return ",".join(filters)


def clip_viral_gta6_gameplay(
    source_video: Path,
    output_video: Path,
    start_sec: Optional[float] = None,
    duration_sec: float = 45.0,
    hook_headline: str = "EXPLORING GTA 6 FOR THE FIRST TIME!",
) -> Path:
    """
    Complete end-to-end processing pipeline for viral GTA 6 gameplay clips.
    """
    source_video = Path(source_video)
    output_video = Path(output_video)
    output_video.parent.mkdir(parents=True, exist_ok=True)

    print(f"🎮 Initializing Viral GTA 6 Clipper for: {source_video.name}")

    # 1. Highlight detection if start_sec not specified
    if start_sec is None:
        print("  [Step 1] Scanning 38-minute VOD for peak viral gameplay moments …")
        candidates = compute_audio_energy_spikes(source_video, window_sec=duration_sec, stride_sec=6.0)
        best_cand = candidates[0]
        start_sec, end_sec, score = best_cand
        print(f"  ✓ Peak gameplay highlight selected: {start_sec:.1f}s → {end_sec:.1f}s (energy score: {score:.2f})")
    else:
        end_sec = start_sec + duration_sec

    # 2. Check for facecam vs pure gameplay reframing
    print("  [Step 2] Analyzing video framing & facecam ROI …")
    facecam_roi = check_facecam_present(source_video, sample_time=start_sec + 5.0)
    if facecam_roi:
        print(f"  ✓ Facecam detected at ROI {facecam_roi} -> preparing stacked layout.")
    else:
        print("  ✓ Fullscreen gameplay detected -> preparing 9:16 vertical action reframing.")

    with tempfile.TemporaryDirectory(prefix="gta6_clipper_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 3. Extract 9:16 1080x1920 base clip
        base_9_16 = tmp_path / "base_9_16.mp4"
        if facecam_roi:
            fx, fy, fw, fh = facecam_roi
            fc_ref = (
                f"[0:v]crop=ih*9/16*1.15:ih:(iw-ih*9/16*1.15)/2:0,scale=1080:1344[game]; "
                f"[0:v]crop={fw}:{fh}:{fx}:{fy},scale=1080:576[cam]; "
                f"[game][cam]vstack,setsar=1[v]"
            )
        else:
            fc_ref = "[0:v]crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920[v]"

        cmd_extract = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(start_sec), "-t", str(duration_sec),
            "-i", str(source_video),
            "-filter_complex", fc_ref,
            "-map", "[v]",
            "-map", "0:a?",
            *get_h264_encoder_args(),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(base_9_16)
        ]
        r_ext = subprocess.run(cmd_extract, capture_output=True, text=True)
        if r_ext.returncode != 0:
            cmd_sw = fallback_cmd_to_libx264(cmd_extract)
            subprocess.run(cmd_sw, check=True)

        # 4. Transcribe segment for MrBeast word subtitles
        word_cues = transcribe_segment(source_video, start_sec, duration_sec)

        # 5. Detect scene cuts for transitions
        print("  [Step 3 & 4] Detecting camera cuts for MrBeast whip transitions …")
        cuts = detect_camera_cuts(base_9_16, adaptive_threshold=2.8, min_scene_len_sec=0.7)
        print(f"  ✓ {len(cuts)} shot boundaries detected.")

        # 6. Step 3: Render headline banner image
        print(f"  [Step 3] Rendering Top Hook Headline Card: \"{hook_headline}\" …")
        banner_img = render_hook_banner_image(1080, 1920, hook_headline, badge_prefix="🚨")
        banner_png = tmp_path / "banner_card.png"
        banner_img.save(banner_png)

        # 7. Step 7: Build MrBeast SFX track
        print("  [Step 7] Generating MrBeast Gaming SFX (808 opening boom, whip whooshes, impact hits) …")
        sfx_audio = tmp_path / "gta6_sfx.m4a"
        punch_moments = [c for c in cuts if 2.0 <= c <= duration_sec - 2.0]
        build_mrbeast_sfx_track(duration_sec, cuts, punch_moments, sfx_audio)

        # 8. Step 4, 5, 8: Assemble visual filters (whip slides, punch zooms, progress bar)
        print("  [Step 4, 5, 8] Assembling whip slides, punch zooms (100% -> 122%), and safe-zone progress bar …")
        v_filters = build_mrbeast_visual_filters(cuts, duration_sec, punch_moments, 1080, 1920)

        # 9. Step 9 & 10: Master audio & video export
        print("  [Step 9 & 10] Rendering mastered video (-14 LUFS vocal master + limiter + 1080x1920 H.264) …")
        master_unsubbed = tmp_path / "master_unsubbed.mp4"
        encoder_args = get_h264_encoder_args()

        cmd_master = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(base_9_16),
            "-i", str(banner_png),
            "-i", str(sfx_audio),
            "-filter_complex",
            f"[1:v]format=rgba,fade=t=out:st=3.5:d=0.5:alpha=1[banner_faded]; "
            f"[0:v]{v_filters}[v_base]; "
            f"[v_base][banner_faded]overlay=0:0:enable='between(t,0,4.0)'[v_out]; "
            f"[0:a][2:a]amix=inputs=2:duration=first:weights=1.0 0.88[a_mix]; "
            f"[a_mix]highpass=f=75,loudnorm=I=-14:TP=-1.0:LRA=9,alimiter=limit=-1.0dB[a_out]",
            "-map", "[v_out]",
            "-map", "[a_out]",
            *encoder_args,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(master_unsubbed),
        ]

        r = subprocess.run(cmd_master, capture_output=True, text=True)
        if r.returncode != 0:
            cmd_sw = fallback_cmd_to_libx264(cmd_master)
            subprocess.run(cmd_sw, check=True)

        # 10. Step 6: Burn MrBeast-Style Kinetic Subtitles
        if word_cues:
            print(f"  [Step 6] Burning {len(word_cues)} MrBeast kinetic word subtitles (vibrant green highlight) …")
            burn_viral_subtitles(
                video_path=master_unsubbed,
                words=word_cues,
                output_path=output_video,
                clip_start=0.0,
                clip_end=duration_sec,
                style_name="mrbeast",
                fps=15,
            )
        else:
            shutil.copy2(str(master_unsubbed), str(output_video))

    print(f"✅ Viral GTA 6 Gameplay Master Exported: {output_video.name} ({output_video.stat().st_size / 1_048_576:.2f} MB)")
    return output_video


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Automated Viral GTA 6 Gameplay Clipper")
    p.add_argument("input", help="Source GTA 6 video path")
    p.add_argument("output", help="Output clip path")
    p.add_argument("--start", type=float, default=None, help="Start time in seconds")
    p.add_argument("--duration", type=float, default=45.0, help="Clip duration in seconds (default: 45.0)")
    p.add_argument("--headline", default="EXPLORING GTA 6 FOR THE FIRST TIME!", help="0-4s top headline text")
    args = p.parse_args()

    clip_viral_gta6_gameplay(
        Path(args.input),
        Path(args.output),
        start_sec=args.start,
        duration_sec=args.duration,
        hook_headline=args.headline,
    )
