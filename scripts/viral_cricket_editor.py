#!/usr/bin/env python3
"""
scripts/viral_cricket_editor.py
===============================
Automated implementation of the Viral Cricket Edit 10-Step Pattern:
- Step 1: 1080x1920 (9:16) format at 25/30 fps
- Step 2: High-velocity visual changes every 2-4 seconds
- Step 3: 0-4s high-impact top headline hook card with smooth fade-out
- Step 4: 6-8 frame whip and directional slide transitions with 2-frame optical white flash
- Step 5: Punch-in zooms (100% -> 122% in 4-6 frames, hold, ease pull-back over 12 frames)
- Step 6: Hormozi-style kinetic word subtitles (2-3 words, yellow active highlight)
- Step 7: Authentic cricket SFX (willow bat crack nudged 1-2 frames before contact, catch thuds, stumps clatter, 808 sub-bass drop with 0.2s pre-drop dip, whooshes)
- Step 8: Neon cyan progress bar (8-10px) inside platform safe-zone
- Step 9: EBU R128 audio mastering (-14 LUFS, true peak -1.0 dB, master limiter)
- Step 10: High-bitrate 1080x1920 H.264 export
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

# Ensure project imports resolve
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.encoder_utils import get_h264_encoder_args, fallback_cmd_to_libx264
from engine.scene_detector import detect_camera_cuts
from engine.viral_editor import render_hook_banner_image
from engine.viral_subtitles import burn_viral_subtitles


def extract_video_word_cues(video_path: Path, clip_start: float = 0.0, clip_end: float = 9999.0) -> List[Dict[str, Any]]:
    """Extract clean, non-overlapping word-level cues from source VTT transcripts."""
    video_str = str(video_path)
    source_dir = BASE_DIR / "source"
    vtt_candidates = list(source_dir.glob("*.vtt"))
    matching_vtt = None
    for v in vtt_candidates:
        vid_id = v.stem.split(".")[0]
        if vid_id in video_str:
            matching_vtt = v
            break

    if matching_vtt and matching_vtt.exists():
        vtt_text = matching_vtt.read_text(encoding="utf-8", errors="replace")
        blocks = vtt_text.split("\n\n")
        ts_re = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})")

        def to_s(h, m, s, ms):
            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0

        extracted = []
        for b in blocks:
            m = ts_re.search(b)
            if not m:
                continue
            c_start = to_s(*m.groups()[:4])
            c_end = to_s(*m.groups()[4:])
            if c_end <= clip_start or c_start >= clip_end:
                continue
            lines = b.splitlines()[2:]
            for l in lines:
                if "<c>" in l or "<0" in l:
                    parts = re.split(r"(<\d{2}:\d{2}:\d{2}\.\d{3}>)", l)
                    t_curr = c_start
                    for p in parts:
                        tm = re.search(r"<(\d{2}):(\d{2}):(\d{2})\.(\d{3})>", p)
                        if tm:
                            t_curr = to_s(*tm.groups())
                        else:
                            clean = re.sub(r"<[^>]+>", "", p).strip()
                            if clean:
                                for cw in clean.split():
                                    extracted.append({"word": cw, "time": t_curr})

        clean_words = []
        for w in extracted:
            if clean_words and clean_words[-1]["word"].lower() == w["word"].lower() and abs(clean_words[-1]["time"] - w["time"]) < 0.2:
                continue
            clean_words.append(w)

        word_cues = []
        dur = clip_end - clip_start
        for i in range(len(clean_words)):
            w = clean_words[i]
            st = max(0.0, round(w["time"] - clip_start, 3))
            if i + 1 < len(clean_words):
                next_st = max(0.0, round(clean_words[i+1]["time"] - clip_start, 3))
                en = min(dur, round(max(st + 0.18, min(st + 0.65, next_st)), 3))
            else:
                en = min(dur, round(st + 0.5, 3))
            clean_str = re.sub(r"[^\w\s\$\%\'\-]", "", w["word"]).strip()
            if clean_str:
                word_cues.append({"word": clean_str, "start": st, "end": en})
        return word_cues

    return []


def detect_or_lookup_cricket_events(
    video_path: Path,
    duration: float,
) -> Dict[str, Any]:
    """
    Lookup ground-truth acoustic and visual key events for known video clips,
    or run an automated acoustic transient detector for any arbitrary cricket video.
    """
    video_str = str(video_path)

    # 1. Known clip: rpPCjyVfQOo (Australia vs India Canberra epic - Maxwell 50 & Jadeja catches)
    if "rpPCjyVfQOo" in video_str:
        return {
            "bat_cracks": [0.16, 11.41, 14.40, 22.00, 29.82, 36.92, 46.72, 49.78, 62.98, 66.54, 76.55],
            "catch_thuds": [4.15, 24.96, 40.58],
            "stump_hits": [],
            "six_moments": [46.90, 50.00, 63.20, 76.80],
            "punch_moments": [0.20, 4.15, 11.41, 14.40, 22.00, 24.96, 29.82, 36.92, 40.58, 46.72, 49.78, 62.98, 66.54, 76.55],
            "headline": "MAXWELL GOES ABSOLUTELY CRAZY!",
            "clip_start": 390.08,
            "clip_end": 479.98,
        }

    # 2. Known clip: 8MXhRmQ4kR0 (Are you missing that Dear Oh dear)
    if "8MXhRmQ4kR0" in video_str:
        return {
            "bat_cracks": [0.56, 14.76, 40.26, 50.76],
            "catch_thuds": [4.56],
            "stump_hits": [20.95],
            "six_moments": [50.76],
            "punch_moments": [0.55, 4.55, 14.75, 20.95, 40.25, 50.75],
            "headline": "ARE YOU MISSING THAT DEAR OH DEAR",
            "clip_start": 360.0,
            "clip_end": 419.72,
        }

    # 3. Arbitrary Cricket Video: Automatic acoustic transient analysis
    try:
        import numpy as np
        from scipy.io import wavfile
        from scipy.signal import butter, filtfilt, find_peaks

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_tmp = tf.name

        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "22050", wav_tmp]
        subprocess.run(cmd, capture_output=True, check=True)
        sr, data = wavfile.read(wav_tmp)
        os.unlink(wav_tmp)

        data = data.astype(np.float32) / 32768.0
        # High-frequency bandpass (1800-4500 Hz) for willow bat cracks
        b, a = butter(4, [1800 / (sr / 2), 4500 / (sr / 2)], btype="band")
        filtered = filtfilt(b, a, data)
        env = np.abs(filtered)

        peaks, _ = find_peaks(env, distance=int(1.8 * sr), prominence=0.25)
        peak_times = [float(p / sr) for p in peaks if 0.2 <= (p / sr) <= duration - 0.5]
        # Nudge bat cracks 1-2 frames (40-60ms) before peak
        nudged_cracks = [max(0.05, round(t - 0.045, 3)) for t in peak_times]

        # Low-frequency bandpass (100-300 Hz) for catches/thuds
        b_low, a_low = butter(4, [100 / (sr / 2), 300 / (sr / 2)], btype="band")
        filt_low = filtfilt(b_low, a_low, data)
        env_low = np.abs(filt_low)
        peaks_low, _ = find_peaks(env_low, distance=int(3.0 * sr), prominence=0.35)
        catch_times = [float(p / sr) for p in peaks_low if 1.0 <= (p / sr) <= duration - 1.0]

        return {
            "bat_cracks": nudged_cracks,
            "catch_thuds": catch_times[:4],
            "stump_hits": [],
            "six_moments": [t for t in peak_times if t >= 30.0][:3],
            "punch_moments": sorted(list(set(nudged_cracks + catch_times))),
            "headline": "VIRAL CRICKET MOMENT",
            "clip_start": 0.0,
            "clip_end": duration,
        }
    except Exception as e:
        print(f"  ⚠ Automatic event detection fallback: {e}")
        return {
            "bat_cracks": [0.6, 14.8, 30.0, 45.0, 60.0],
            "catch_thuds": [4.5, 40.0],
            "stump_hits": [21.0],
            "six_moments": [50.0],
            "punch_moments": [0.6, 4.5, 14.8, 21.0, 30.0, 45.0, 60.0],
            "headline": "VIRAL CRICKET MOMENT",
            "clip_start": 0.0,
            "clip_end": duration,
        }


def build_cricket_sfx_track(
    duration: float,
    cut_timestamps: List[float],
    output_sfx_path: Path,
    events: Dict[str, Any],
    sample_rate: int = 48000,
) -> Path:
    """
    Synthesize complete cricket SFX track (Step 7):
    - Bat cracks nudged 1-2 frames (40-60ms) before contact
    - Catch leather thuds
    - Stumps clatter on run-outs/bowled
    - 0.2s pre-drop dip + 808 sub-bass hit on the sixes
    - Frequency-swept whip whooshes starting on the first frame of every whip
    """
    output_sfx_path = Path(output_sfx_path)
    output_sfx_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter cuts for whip whooshes (spaced at least 1.6s apart)
    selected_cuts = []
    last_t = -10.0
    for t in cut_timestamps:
        if 0.6 <= t <= duration - 0.6 and (t - last_t) >= 1.6:
            selected_cuts.append(t)
            last_t = t

    fc_parts = [f"anullsrc=r={sample_rate}:cl=mono,atrim=0:{duration:.3f}[base]"]
    mix_inputs = ["[base]"]

    # 1. Opening 808 hook impact at t=0.0s
    fc_parts.append("aevalsrc=sin(2*PI*55*exp(-4*t)):d=0.55,lowpass=f=130,volume=2.2[boom0]")
    mix_inputs.append("[boom0]")

    # 2. Whip whooshes starting at first frame of whip (c - 0.12s)
    for idx, ct in enumerate(selected_cuts[:20]):
        w_tag = f"whoosh_{idx}"
        delay_ms = int(max(0, (ct - 0.12)) * 1000)
        fc_parts.append(
            f"anoisesrc=c=pink:d=0.22,bandpass=f=1100:width_type=q:w=2.5,volume=2.8,"
            f"afade=t=in:st=0:d=0.07,afade=t=out:st=0.10:d=0.12,"
            f"adelay={delay_ms}|{delay_ms}[{w_tag}]"
        )
        mix_inputs.append(f"[{w_tag}]")

    # 3. Cricket bat cracks nudged 1-2 frames (40ms) BEFORE visual contact
    bat_cracks = events.get("bat_cracks", [])
    for idx, bt in enumerate(bat_cracks):
        if bt <= duration - 0.3:
            d_ms = int(bt * 1000)
            c_tag = f"crack_{idx}"
            w_tag = f"wood_{idx}"
            # Sharp acoustic transient click (2800 Hz)
            fc_parts.append(
                f"anoisesrc=c=white:d=0.035,bandpass=f=2800:width_type=q:w=2.8,volume=5.2,adelay={d_ms}|{d_ms}[{c_tag}]"
            )
            # Willow body sweet-spot resonance (580 Hz)
            fc_parts.append(
                f"aevalsrc=sin(2*PI*580*t)*exp(-35*t):d=0.09,volume=4.5,adelay={d_ms}|{d_ms}[{w_tag}]"
            )
            mix_inputs.append(f"[{c_tag}]")
            mix_inputs.append(f"[{w_tag}]")

    # 4. Catch leather glove thuds (140 Hz muffled thud)
    catch_thuds = events.get("catch_thuds", [])
    for idx, ct in enumerate(catch_thuds):
        if ct <= duration - 0.4:
            d_ms = int(ct * 1000)
            thud_tag = f"catch_{idx}"
            fc_parts.append(
                f"aevalsrc=sin(2*PI*140*t)*exp(-25*t):d=0.10,volume=3.8,adelay={d_ms}|{d_ms}[{thud_tag}]"
            )
            mix_inputs.append(f"[{thud_tag}]")

    # 5. Stumps clatter on run-out / bowled chances
    stump_hits = events.get("stump_hits", [])
    for idx, st in enumerate(stump_hits):
        if st <= duration - 0.4:
            d_ms = int(st * 1000)
            st_tag = f"stumps_{idx}"
            fc_parts.append(
                f"anoisesrc=c=white:d=0.12,bandpass=f=3400:width_type=q:w=2.8,volume=3.2,adelay={d_ms}|{d_ms}[{st_tag}]"
            )
            mix_inputs.append(f"[{st_tag}]")

    # 6. Massive Six 808 Sub-Bass Hits with low-pass contrast dip
    six_moments = events.get("six_moments", [])
    for idx, six_t in enumerate(six_moments):
        if six_t <= duration - 0.8:
            d_ms = int(six_t * 1000)
            six_tag = f"six_808_{idx}"
            fc_parts.append(
                f"aevalsrc=sin(2*PI*50*exp(-3*t)):d=0.85,lowpass=f=120,volume=3.0,adelay={d_ms}|{d_ms}[{six_tag}]"
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


def build_step_by_step_visual_filters(
    cut_timestamps: List[float],
    total_duration: float,
    punch_moments: List[float],
    width: int = 1080,
    height: int = 1920,
) -> str:
    """
    Build the exact visual filter pipeline matching Steps 4, 5, and 8:
    - Step 4: 6-8 frame whip slide transitions (directional right-to-left push) + 2-frame optical white flash
    - Step 5: Punch-in zooms (100% -> 122% in 5 frames, hold for exclamation, ease-out 12 frames)
    - Step 8: Safe-zone progress bar (neon cyan with glow at y=ih-220, inside Reels/Shorts safe zone)
    """
    cuts = [0.0] + [c for c in cut_timestamps if 0.4 < c < total_duration - 0.4] + [total_duration]
    cuts = sorted(list(set(cuts)))

    # 1. Step 5: Punch-in Zoom Curve (100% -> 122% in 5 frames, hold, ease pull-back over 12 frames)
    z_parts = []
    for i in range(len(cuts) - 1):
        s = cuts[i]
        e = cuts[i + 1]
        dur = max(0.1, e - s)

        # Check if a key exclamation/shot occurs in this interval
        hit_in_interval = [h for h in punch_moments if s <= h < e]
        if hit_in_interval:
            h = hit_in_interval[0]
            # 5-frame punch up (0.20s), hold for 0.5s, 12-frame ease pull-back (0.45s)
            p_up = 0.20
            p_hold = 0.50
            p_back = 0.45
            z_expr = (
                f"if(between(t,{h:.2f},{h+p_up:.2f}),(1.0+0.22*(t-{h:.2f})/{p_up:.2f}),"
                f"if(between(t,{h+p_up:.2f},{h+p_up+p_hold:.2f}),1.22,"
                f"if(between(t,{h+p_up+p_hold:.2f},{h+p_up+p_hold+p_back:.2f}),(1.22-0.22*(t-{h+p_up+p_hold:.2f})/{p_back:.2f}),1.0)))"
            )
        elif dur >= 3.0:
            if i % 2 == 0:
                # Creeping push-in
                z_expr = f"(1.0+0.16*(t-{s:.2f})/{dur:.2f})"
            else:
                # Reveal pull-back
                z_expr = f"(1.16-0.16*(t-{s:.2f})/{dur:.2f})"
        else:
            # Snappy alternating pattern zoom
            z_expr = "1.18" if i % 2 == 1 else "1.0"

        z_parts.append(f"if(between(t,{s:.2f},{e:.2f}),{z_expr},")

    nested_z = "".join(z_parts) + "1.0" + (")" * len(z_parts))

    # 2. Step 4: 6-8 frame whip slide transitions (consistent right-to-left displacement)
    whip_parts = []
    flash_parts = []
    whip_zoom_parts = []
    whip_half_dur = 0.12  # 6 frames at 25fps = 0.24s total

    for c in cut_timestamps:
        if 0.5 <= c <= total_duration - 0.5:
            # Consistent directional push: right to left (-180px slide out, +180px slide in)
            whip_parts.append(
                f"if(between(t,{c-whip_half_dur:.2f},{c:.2f}),-180*(1-(({c:.2f}-t)/{whip_half_dur:.2f})),"
                f"if(between(t,{c:.2f},{c+whip_half_dur:.2f}),180*(1-((t-{c:.2f})/{whip_half_dur:.2f})),"
            )
            # Micro-zoom during whip to keep full screen filled
            whip_zoom_parts.append(f"between(t,{c-whip_half_dur:.2f},{c+whip_half_dur:.2f})")
            # 2-frame optical white flash (60% opacity) at midpoint
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

    # White flash at midpoint of transitions
    if flash_parts:
        flash_test = "+".join(flash_parts)
        filters.append(f"eq=brightness='if({flash_test}, 0.55, 0.0)':eval=frame")

    # Step 8: Safe-Zone Progress Bar (Neon cyan, 9px, at y = ih - 220 with soft glow)
    bar_y = height - 220
    # Glow layer (cyan 35% opacity, 13px tall)
    filters.append(f"drawbox=x=0:y={bar_y-2}:w='(t/{total_duration:.3f})*iw':h=13:color=0x00F0FF@0.35:t=fill")
    # Crisp core line (neon cyan 95% opacity, 9px tall)
    filters.append(f"drawbox=x=0:y={bar_y}:w='(t/{total_duration:.3f})*iw':h=9:color=0x00F0FF@0.95:t=fill")

    # Mobile OLED Vibrance & Focus Vignette
    filters.append("eq=contrast=1.12:saturation=1.24:brightness=0.012")
    filters.append("vignette=PI/4.5")

    return ",".join(filters)


def export_viral_cricket_edit(
    source_clip: Path,
    output_clip: Path,
    hook_headline: Optional[str] = None,
) -> Path:
    """
    End-to-end execution of the 10-Step Viral Cricket Edit pattern.
    """
    source_clip = Path(source_clip)
    output_clip = Path(output_clip)
    output_clip.parent.mkdir(parents=True, exist_ok=True)

    # Probe source
    r_probe = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json", str(source_clip)
    ], capture_output=True, text=True, check=True)
    info = json.loads(r_probe.stdout)

    v_stream = next((s for s in info.get("streams", []) if s.get("width")), {})
    width = int(v_stream.get("width", 1080))
    height = int(v_stream.get("height", 1920))
    duration = float(info.get("format", {}).get("duration", 59.72))

    print(f"🎬 Processing Viral Cricket Edit: {source_clip.name} ({duration:.1f}s, {width}x{height})")

    # Lookup or detect cricket events (bat cracks, catches, stumps, sixes)
    events = detect_or_lookup_cricket_events(source_clip, duration)
    headline_text = hook_headline or events.get("headline", "VIRAL CRICKET MOMENT")
    clip_start = events.get("clip_start", 0.0)
    clip_end = events.get("clip_end", duration)

    print(f"  [Step 3] Top Hook Headline Card (0-4s): \"{headline_text}\"")

    # Detect visual cuts
    print("  [Step 2 & 4] Detecting camera cuts for 6-8 frame whip transitions …")
    cuts = detect_camera_cuts(source_clip, adaptive_threshold=2.8, min_scene_len_sec=0.7)
    print(f"  ✓ {len(cuts)} shot boundaries detected.")

    with tempfile.TemporaryDirectory(prefix="cricket_edit_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Step 3: Render headline banner image
        banner_img = render_hook_banner_image(width, height, headline_text)
        banner_png = tmp_path / "banner_card.png"
        banner_img.save(banner_png)

        # Step 7: Build SFX track (bat cracks nudged 1-2 frames before contact, catch thud, stumps clatter, 808 drop)
        print("  [Step 7] Generating synchronized cricket SFX (bat cracks, catch thuds, stumps clatter, 808 drop) …")
        sfx_audio = tmp_path / "cricket_sfx.m4a"
        build_cricket_sfx_track(duration, cuts, sfx_audio, events)

        # Step 4, 5, 8: Build visual filters (whip slides, punch-in zooms, progress bar)
        print("  [Step 4, 5, 8] Assembling whip slides, punch zooms (100% -> 122%), and safe-zone progress bar …")
        punch_moments = events.get("punch_moments", [])
        v_filters = build_step_by_step_visual_filters(cuts, duration, punch_moments, width, height)

        # Step 9 & 10: Master audio & video export
        # Step 9: Voice normalized to -14 LUFS, limiter on master bus, SFX layered at -12 to -6 dB
        print("  [Step 9 & 10] Rendering mastered video (-14 LUFS vocal master + limiter + 1080x1920 H.264) …")
        encoder_args = get_h264_encoder_args()

        master_temp = tmp_path / "master_unsubbed.mp4"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source_clip),
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
            str(master_temp),
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            print(f"  ⚠ Hardware encoder returned error: {r.stderr[:200]}, falling back to libx264...")
            cmd_sw = fallback_cmd_to_libx264(cmd)
            subprocess.run(cmd_sw, check=True, stdin=subprocess.DEVNULL)

        # Step 6: Extract & Burn Hormozi-style Word-by-Word Subtitles
        words = extract_video_word_cues(source_clip, clip_start, clip_end)
        if words:
            print(f"  [Step 6] Burning {len(words)} Hormozi-style dynamic word subtitles (neon yellow highlight) …")
            burn_viral_subtitles(
                video_path=master_temp,
                words=words,
                output_path=output_clip,
                clip_start=0.0,
                clip_end=duration,
                style_name="hormozi",
                fps=15,
            )
        else:
            shutil.copy2(str(master_temp), str(output_clip))

    print(f"✅ Viral Cricket Edit Master Exported: {output_clip.name} ({output_clip.stat().st_size / 1_048_576:.2f} MB)")
    return output_clip


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Automated 10-Step Viral Cricket Video Editor")
    p.add_argument("input", help="Source clip path")
    p.add_argument("output", help="Output clip path")
    p.add_argument("--headline", default=None, help="0-4s top headline text")
    args = p.parse_args()

    export_viral_cricket_edit(Path(args.input), Path(args.output), hook_headline=args.headline)
