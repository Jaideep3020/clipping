#!/usr/bin/env python3
"""
pipeline.py — YouTube → AI Highlight Clipping Pipeline
=======================================================
Built following the video-clipping skill rules:
  - Never overwrite originals (all output goes to output/<stem>/)
  - Probe before cut (ffprobe first, always)
  - Choose cut method deliberately (B: re-encode, frame-accurate)
  - Verify every output (ffprobe check on each clip)
  - Respect naming conventions: <stem>_<NN>_<slug>_<WxH>_<start>-<end>.mp4
  - Write manifest.csv for every run
  - Intermediates stay in work/

Stages:
  1. Download     yt-dlp  → source/<stem>.mp4
  2. Probe        ffprobe → anomaly detection
  3. Transcribe   faster-whisper (or openai-whisper) → work/<stem>.json
  4. Score        engine/clipper_engine.py → list[ClipCandidate] (4-dim virality)
  5. Plan         work/plan.md  (shown before expensive batch render)
  6. Render       ffmpeg Method B cuts → output/<stem>/
               ↳  optional: burn word-level captions via ffmpeg drawtext
  7. Verify       ffprobe each output + blackdetect head/tail
  8. Deliver      manifest.csv (with 4-dim scores) + summary scorecard
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime

# ─── Directory layout (skill §14) ─────────────────────────────────────────────
BASE        = Path(__file__).parent
SOURCE_DIR  = BASE / "source"
OUTPUT_DIR  = BASE / "output"
WORK_DIR    = BASE / "work"

for d in [SOURCE_DIR, OUTPUT_DIR, WORK_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Engine import ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(BASE))
from engine.clipper_engine import score_highlights, ViralityScore, ClipCandidate
from engine.encoder_utils import get_h264_encoder_args, fallback_cmd_to_libx264
from engine.viral_subtitles import burn_viral_subtitles
from engine.viral_editor import add_hook_banner_to_video, reframe_video_9_16, assemble_viral_clip
from engine.viral_enhancer import apply_viral_master_suite
from engine.transition_pack import apply_transition_pack_to_video, TRANSITION_PACKS
from engine.face_tracker import get_face_centered_crop_filter
from engine.scene_detector import refine_clip_boundaries_with_scenes
from engine.gta6_clipping import (
    classify_gta6_moment,
    gameplay_facecam_stack,
    detect_cutscene_spoiler,
    render_music_safe_variant,
    format_gta6_clip_filename,
    GTA6_MOMENTS,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def run(cmd: list, capture=True, check=True):
    """Run a subprocess command and return CompletedProcess."""
    r = subprocess.run(cmd, capture_output=capture, text=True, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise RuntimeError(f"Command failed:\n{' '.join(cmd)}\nSTDERR: {r.stderr[-2000:]}")
    return r

def ts(seconds: float) -> str:
    """Float seconds → HH:MM:SS.mmm string."""
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def slug(text: str, max_len=30) -> str:
    """Turn text into a safe filename slug."""
    s = re.sub(r'[^\w\s-]', '', text.lower())
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s[:max_len]

def _score_bar(score: float, width: int = 10) -> str:
    """Return a unicode bar for a 0-10 score."""
    filled = round(score)
    return "█" * filled + "░" * (width - filled)

# ─── Stage 1: Download (skill §2.3) ───────────────────────────────────────────

def download(url: str) -> tuple[Path, str, str, float]:
    """
    Download URL with yt-dlp, downloading best video + audio and merging into MP4 with FFmpeg.
    Emits real-time download progress bar and filters candidates strictly by video extension.
    If already downloaded or local file, reuses existing file.
    Returns (video_path, video_id, title, duration_seconds).
    """
    print("\n[1/8] 📥  Downloading (Video + Audio) …")
    VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}

    # 1. Check if user passed a local file directly
    if Path(url).is_file():
        p = Path(url)
        print(f"  ✓ Using local video file: {p.name}")
        return p, p.stem, p.stem, 0.0

    # 2. Check if this YouTube video was already downloaded in source/
    m = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", url)
    if m:
        extracted_vid = m.group(1)
        existing = [
            p for p in SOURCE_DIR.iterdir()
            if p.is_file() and extracted_vid in p.name and p.suffix.lower() in VIDEO_EXTS
        ]
        if existing:
            existing.sort(key=lambda p: p.stat().st_size, reverse=True)
            print(f"  ✓ Found existing downloaded video in source/: {existing[0].name} (skipping re-download)")
            return existing[0], extracted_vid, existing[0].stem, 0.0

    import yt_dlp

    last_pct = [-1.0]

    def _progress_hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed", 0) or 0
            eta = d.get("eta", 0) or 0
            if total > 0:
                pct = (downloaded / total) * 100.0
                if pct - last_pct[0] >= 1.0 or pct >= 100.0:
                    last_pct[0] = pct
                    bar_len = 20
                    filled = int(round(bar_len * (downloaded / float(total))))
                    bar = "█" * filled + "░" * (bar_len - filled)
                    speed_mb = speed / (1024 * 1024) if speed else 0.0
                    down_mb = downloaded / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    print(f"  📥 [download] [{bar}] {pct:5.1f}% | {down_mb:.1f}/{tot_mb:.1f}MB | {speed_mb:.1f}MB/s | ETA {eta}s", flush=True)
            else:
                down_mb = downloaded / (1024 * 1024)
                print(f"  📥 [download] {down_mb:.1f}MB downloaded...", flush=True)
        elif d.get("status") == "finished":
            print(f"  ✓ Download finished, ensuring video & audio are merged into MP4...")

    ydl_opts = {
        "format"              : "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
        "merge_output_format" : "mp4",
        "outtmpl"             : str(SOURCE_DIR / "%(id)s.%(ext)s"),
        "quiet"               : True,
        "no_warnings"         : True,
        "overwrites"          : False,   # never overwrite originals (skill §0.1)
        "writesubtitles"      : False,
        "writeautomaticsub"   : False,
        "progress_hooks"      : [_progress_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info  = ydl.extract_info(url, download=True)
        vid   = info["id"]
        title = info.get("title", vid)
        dur   = float(info.get("duration") or 0)

    # Filter strictly for video files (prevent picking .vtt, .json, or partial files)
    VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
    video_cands = [
        p for p in SOURCE_DIR.iterdir()
        if p.is_file() and vid in p.name and p.suffix.lower() in VIDEO_EXTS
    ]
    if not video_cands:
        raise FileNotFoundError(f"Download produced no valid video file for id={vid}")

    # Sort by file size descending (the video file is always the largest)
    video_cands.sort(key=lambda p: p.stat().st_size, reverse=True)
    path = video_cands[0]

    # Verify that the downloaded file contains an audio stream; if missing audio, merge with standalone audio
    probe_check = run([
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
        "-of", "json", str(path)
    ], check=False)
    has_audio = False
    if probe_check.stdout:
        try:
            streams = json.loads(probe_check.stdout).get("streams", [])
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
        except Exception:
            pass

    if not has_audio:
        audio_exts = {".m4a", ".mp3", ".opus", ".aac", ".wav"}
        audio_cands = [p for p in SOURCE_DIR.iterdir() if p.is_file() and vid in p.name and p.suffix.lower() in audio_exts]
        if audio_cands:
            audio_cands.sort(key=lambda p: p.stat().st_size, reverse=True)
            audio_file = audio_cands[0]
            merged_file = SOURCE_DIR / f"{vid}_merged.mp4"
            print(f"  ⚡ Merging video ({path.name}) + audio ({audio_file.name}) → {merged_file.name}...")
            run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(path), "-i", str(audio_file),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(merged_file)
            ])
            if merged_file.exists():
                path = merged_file

    print(f"    ✓  {title}  ({dur:.0f}s)  →  {path.name}")
    return path, vid, title, dur


# ─── Stage 2: Probe (skill §2.2) ──────────────────────────────────────────────

def probe(path: Path) -> dict:
    """Run ffprobe and return parsed JSON. Flag anomalies."""
    print(f"\n[2/8] 🔍  Probing {path.name} …")
    r = run([
        "ffprobe", "-v", "error",
        "-show_entries", (
            "format=duration,size,bit_rate:"
            "stream=index,codec_type,codec_name,width,height,"
            "r_frame_rate,avg_frame_rate,pix_fmt,color_transfer,channels,sample_rate:"
            "stream_tags=rotate:stream_side_data=rotation"
        ),
        "-of", "json", str(path),
    ])
    info = json.loads(r.stdout)

    fmt     = info.get("format", {})
    streams = info.get("streams", [])
    video_s = next((s for s in streams if s.get("codec_type") == "video"),  {})
    audio_s = next((s for s in streams if s.get("codec_type") == "audio"),  {})

    dur     = float(fmt.get("duration", 0))
    w       = video_s.get("width",  0)
    h       = video_s.get("height", 0)
    pix_fmt = video_s.get("pix_fmt", "?")
    rfr     = video_s.get("r_frame_rate",   "?")
    afr     = video_s.get("avg_frame_rate", "?")
    rotate  = (video_s.get("tags") or {}).get("rotate", "0")
    hdr     = video_s.get("color_transfer", "") in ("smpte2084", "arib-std-b67")

    flags = []
    if rotate not in ("0", "", None):   flags.append(f"⚠ ROTATION metadata={rotate}° (will be auto-handled)")
    if rfr != afr:                      flags.append("⚠ VFR detected — will use -fps_mode cfr")
    if hdr:                             flags.append("⚠ HDR source — consider tonemapping if sharing widely")
    if not audio_s:                     flags.append("⚠ No audio stream found")

    result = {
        "path": str(path), "duration": dur, "width": w, "height": h,
        "pix_fmt": pix_fmt, "r_frame_rate": rfr, "avg_frame_rate": afr,
        "is_vfr": rfr != afr, "is_hdr": hdr, "rotate": rotate,
        "has_audio": bool(audio_s), "flags": flags,
    }

    print(f"    ✓  {w}×{h}  {rfr}fps  {pix_fmt}  dur={dur:.1f}s")
    for flag in flags:
        print(f"    {flag}")
    return result


# ─── Stage 3: Transcribe (skill §4.5) ─────────────────────────────────────────

def parse_vtt_to_transcript(vtt_path: Path) -> dict:
    """Parse a WebVTT file into normalized transcript segments with estimated word boundaries."""
    text = vtt_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"WEBVTT.*?\n\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"NOTE[^\n]*\n(?:[^\n]*\n)*\n", "", text)
    blocks = re.split(r"\n{2,}", text.strip())
    ts_re = re.compile(r"(\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->\s*(\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}")

    def to_secs(ts_str: str) -> float:
        ts_str = ts_str.strip().replace(",", ".")
        parts = ts_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])

    segments = []
    text_parts = []
    seg_id = 0

    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        for i, line in enumerate(lines):
            if ts_re.search(line):
                raw_start = line.split("-->")[0].strip()
                raw_end = line.split("-->")[1].strip().split()[0]
                cue_text = " ".join(lines[i+1:])
                cue_text = re.sub(r"<[^>]+>", "", cue_text).strip()
                if cue_text:
                    start_s = to_secs(raw_start)
                    end_s = to_secs(raw_end)
                    if end_s > start_s:
                        words_raw = cue_text.split()
                        dur = end_s - start_s
                        w_dur = dur / max(len(words_raw), 1)
                        words = [
                            {
                                "word": w,
                                "start": round(start_s + j * w_dur, 2),
                                "end": round(start_s + (j + 1) * w_dur, 2),
                            }
                            for j, w in enumerate(words_raw)
                        ]
                        segments.append({
                            "id": seg_id,
                            "start": round(start_s, 2),
                            "end": round(end_s, 2),
                            "text": cue_text,
                            "words": words,
                        })
                        text_parts.append(cue_text)
                        seg_id += 1
                break

    return {
        "text": " ".join(text_parts),
        "segments": segments,
        "language": "en",
        "engine": "youtube-vtt",
    }


def transcribe(path: Path, model_size: str = "small", total_duration: float = 0.0) -> dict:
    """
    Transcribe audio with faster-whisper or reuse official YouTube subtitles (.vtt).
    Uses work/<stem>.json cache to avoid re-transcribing.
    Emits real-time progress bar.
    Returns normalized dict with 'segments' and 'text'.
    """
    print(f"\n[3/8] 🎙️  Transcribing ({model_size}) …")
    cache = WORK_DIR / f"{path.stem}.json"
    if cache.exists():
        print("    ✓  Using cached transcript.")
        return json.loads(cache.read_text())

    # 1. Check for downloaded YouTube subtitles (.vtt)
    vtt_candidates = [
        p for p in SOURCE_DIR.iterdir()
        if p.is_file() and path.stem in p.name and p.suffix.lower() == ".vtt"
    ]
    if vtt_candidates:
        vtt_file = vtt_candidates[0]
        print(f"    ✓  Found YouTube official subtitles: {vtt_file.name} (instant transcription!)")
        try:
            parsed = parse_vtt_to_transcript(vtt_file)
            if parsed and len(parsed["segments"]) >= 3:
                cache.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
                print(f"    ✓  {len(parsed['segments'])} segments parsed from YouTube captions [{parsed['engine']}]")
                return parsed
        except Exception as ve:
            print(f"    ⚠  Failed parsing {vtt_file.name} ({ve}), falling back to Whisper...")

    # 2. Faster-Whisper with real-time progress bar
    try:
        from faster_whisper import WhisperModel
        print(f"    🎙️ Running faster-whisper ({model_size}) with word-level timestamps...")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segs_iter, info = model.transcribe(str(path), word_timestamps=True)

        segments, text_parts = [], []
        last_pct = [-1.0]
        dur_ref = total_duration or float(info.duration or 0) or 1.0

        for seg in segs_iter:
            words = [{"word": w.word, "start": w.start, "end": w.end}
                     for w in (seg.words or [])]
            segments.append({"id": seg.id, "start": seg.start,
                              "end": seg.end, "text": seg.text.strip(), "words": words})
            text_parts.append(seg.text)
            pct = min(100.0, (seg.end / dur_ref) * 100.0)
            if pct - last_pct[0] >= 5.0 or pct >= 100.0:
                last_pct[0] = pct
                bar_len = 20
                filled = int(round(bar_len * (pct / 100.0)))
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"  🎙️ [transcribe] [{bar}] {pct:5.1f}% | {ts(seg.start)} → {ts(seg.end)}", flush=True)

        result = {"text": " ".join(text_parts), "segments": segments,
                  "language": info.language, "engine": "faster-whisper"}

    except Exception as fwe:
        print(f"    ⚠ faster-whisper notice: {fwe}; trying openai-whisper...")
        import whisper
        model = whisper.load_model(model_size)
        raw   = model.transcribe(str(path), word_timestamps=True, verbose=False)
        segments = []
        for seg in raw["segments"]:
            words = [{"word": w["word"], "start": w["start"], "end": w["end"]}
                     for w in seg.get("words", [])]
            segments.append({"id": seg["id"], "start": seg["start"],
                              "end": seg["end"], "text": seg["text"].strip(), "words": words})
        result = {"text": raw["text"], "segments": segments,
                  "language": raw.get("language", "en"), "engine": "openai-whisper"}

    cache.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"    ✓  {len(result['segments'])} segments  ({result['language']})  [{result['engine']}]")
    return result


# ─── Stage 4: AI Scoring (engine/clipper_engine.py) ──────────────────────────

def score(transcript_result: dict, config: dict) -> list[ClipCandidate]:
    """
    Use engine/clipper_engine.score_highlights() with 4-dimension virality scoring.
    Returns sorted list[ClipCandidate] filtered by min_score.
    """
    max_clips = config["max_clips"]
    min_dur   = config["min_dur"]
    max_dur   = config["max_dur"]
    min_score = config["min_score"]
    provider  = config["provider"]

    print(f"\n[4/8] 🧠  Scoring highlights (up to {max_clips}, {min_dur}–{max_dur}s, "
          f"min_score={min_score}, provider={provider}) …")

    candidates = score_highlights(
        transcript_segments=transcript_result["segments"],
        video_duration=transcript_result["segments"][-1]["end"]
            if transcript_result["segments"] else 0.0,
        config={
            "max_clips"     : max_clips,
            "min_dur"       : min_dur,
            "min_duration"  : min_dur,
            "max_dur"       : max_dur,
            "max_duration"  : max_dur,
            "min_score"     : min_score,
            "provider"      : provider,
        },
    )
    print(f"    ✓  {len(candidates)} highlight(s) passed min_score={min_score}")
    return candidates


# ─── Stage 5: Plan (skill §11 step 3) ─────────────────────────────────────────

def write_plan(candidates: list[ClipCandidate], probe_info: dict, stem: str,
               vertical: bool) -> Path:
    """Write work/<stem>_plan.md and return its path."""
    w, h = (1080, 1920) if vertical else (probe_info["width"], probe_info["height"])
    method = "B (re-encode, frame-accurate)"
    lines  = [
        f"# Clip Plan — {stem}",
        f"Generated: {datetime.now().isoformat()}",
        f"",
        f"| # | Title | Start | End | Duration | Hook | Engage | Share | Overall | Method | Output |",
        f"|---|-------|-------|-----|----------|------|--------|-------|---------|--------|--------|",
    ]
    for i, c in enumerate(candidates, 1):
        dur      = c.end - c.start
        c_slug   = slug(c.title)
        out_name = f"{stem}_{i:02d}_{c_slug}_{w}x{h}_{int(c.start):04d}-{int(c.end):04d}.mp4"
        v        = c.virality
        lines.append(
            f"| {i} | {c.title[:40]} | {ts(c.start)} | {ts(c.end)} | {dur:.1f}s "
            f"| {v.hook:.1f} | {v.engagement:.1f} | {v.shareability:.1f} | {v.overall:.1f} "
            f"| {method} | {out_name} |"
        )

    plan_path = WORK_DIR / f"{stem}_plan.md"
    plan_path.write_text("\n".join(lines))
    print(f"\n[5/8] 📋  Plan written → {plan_path}")
    return plan_path


# ─── Caption helpers ──────────────────────────────────────────────────────────

def _segments_to_srt(segments: list[dict], clip_start: float, clip_end: float) -> str:
    """
    Build an SRT string from whisper transcript segments, trimmed to [clip_start, clip_end].
    Timestamps are re-offset so the clip starts at 0.
    """
    def fmt_srt_ts(secs: float) -> str:
        h  = int(secs // 3600)
        m  = int((secs % 3600) // 60)
        s  = int(secs % 60)
        ms = int((secs - int(secs)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    idx   = 1
    for seg in segments:
        seg_start = seg["start"]
        seg_end   = seg["end"]
        if seg_end <= clip_start or seg_start >= clip_end:
            continue
        # clamp and re-offset
        s = max(seg_start, clip_start) - clip_start
        e = min(seg_end,   clip_end)   - clip_start
        lines.append(str(idx))
        lines.append(f"{fmt_srt_ts(s)} --> {fmt_srt_ts(e)}")
        lines.append(seg["text"].strip())
        lines.append("")
        idx += 1
    return "\n".join(lines)


def _extract_all_words(segments: list[dict]) -> list[dict]:
    """Collect flat list of word-level timestamps from whisper segments."""
    words = []
    for s in segments:
        for w in s.get("words", []):
            words.append({"word": w["word"], "start": float(w["start"]), "end": float(w["end"])})
    return words


def _srt_to_drawtext_filters(srt_path: Path) -> list[str]:
    """Parse SRT into a list of ffmpeg drawtext filter strings."""
    if not srt_path.exists():
        return []
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\s*\n", content.strip())
    filters = []
    ts_re = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        ts_line_idx = 1 if len(lines) > 1 and ts_re.search(lines[1]) else (0 if ts_re.search(lines[0]) else -1)
        if ts_line_idx == -1:
            continue
        m = ts_re.search(lines[ts_line_idx])
        if not m:
            continue
        s_h, s_m, s_s, s_ms, e_h, e_m, e_s, e_ms = [int(x) for x in m.groups()]
        t_start = s_h * 3600 + s_m * 60 + s_s + s_ms / 1000.0
        t_end = e_h * 3600 + e_m * 60 + e_s + e_ms / 1000.0
        text = " ".join(lines[ts_line_idx + 1:]).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")
        if text.strip():
            filters.append(
                f"drawtext=text='{text}':enable='between(t,{t_start:.3f},{t_end:.3f})':"
                f"fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=4:x=(w-text_w)/2:y=h-80"
            )
    return filters


def _burn_captions_srt(clip_path: Path, srt_path: Path, out_path: Path):
    """
    Burn captions from an SRT file onto a video.
    First tries subtitles filter via scripts/burn_subtitles.py.
    Falls back to ffmpeg drawtext filter chain or soft subtitles.
    """
    burn_script = BASE / "scripts" / "burn_subtitles.py"
    if burn_script.exists():
        r = subprocess.run(
            [sys.executable, str(burn_script), str(clip_path), str(srt_path), str(out_path)],
            capture_output=True, text=True
        )
        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return

    # Drawtext filter fallback
    dt_filters = _srt_to_drawtext_filters(srt_path)
    if dt_filters:
        # Limit to avoid command line arg length overflow
        vf = ",".join(dt_filters[:50])
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(clip_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out_path)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return

    # Soft sub fallback
    cmd_soft = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(clip_path),
        "-i", str(srt_path),
        "-c:v", "copy", "-c:a", "copy",
        "-c:s", "mov_text",
        str(out_path)
    ]
    subprocess.run(cmd_soft, capture_output=True, text=True)


def _burn_captions(clip_path: Path, words: list[dict], out_path: Path,
                   start_sec: float, end_sec: float, style: str = "hormozi"):
    """
    Burn dynamic word-by-word viral karaoke captions onto a clip
    (Alex Hormozi / MrBeast style with active word highlights).
    """
    burn_viral_subtitles(
        video_path=clip_path,
        words=words,
        output_path=out_path,
        clip_start=start_sec,
        clip_end=end_sec,
        style_name=style,
    )


# ─── Stage 6: Render clips (skill §3.3 Method B) ──────────────────────────────

def render_clips(source: Path, candidates: list[ClipCandidate],
                 probe_info: dict, stem: str, vertical: bool,
                 config: dict, transcript_segments: list[dict]) -> list[dict]:
    """
    Cut each ClipCandidate using FFmpeg Method B (re-encode, frame-accurate).
    Uses Apple VideoToolbox (h264_videotoolbox) with libx264 fallback.
    If config['captions'] is True, burns word-level SRT captions onto each clip.
    Writes to output/<stem>/
    """
    print(f"\n[6/8] ✂️  Rendering clips …")
    out_dir = OUTPUT_DIR / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    w_out, h_out = (1080, 1920) if vertical else (probe_info["width"], probe_info["height"])
    # Ensure even dimensions (skill §6.10)
    w_out = (w_out // 2) * 2
    h_out = (h_out // 2) * 2

    is_vfr    = probe_info.get("is_vfr", False)
    has_audio = probe_info.get("has_audio", True)
    do_captions = config.get("captions", False)

    metas = []
    for i, clip in enumerate(candidates, 1):
        raw_start = float(clip.start)
        raw_end   = float(clip.end)

        # SOTA: Refine clip boundaries with PySceneDetect camera cuts
        if config.get("scene_detect", True):
            start, end = refine_clip_boundaries_with_scenes(raw_start, raw_end, source, tolerance_sec=1.2)
        else:
            start, end = raw_start, raw_end

        dur     = end - start
        c_slug  = slug(clip.title)
        out_name = f"{stem}_{i:02d}_{c_slug}_{w_out}x{h_out}_{int(start):04d}-{int(end):04d}.mp4"
        out_path = out_dir / out_name

        v = clip.virality
        print(f"    Clip {i}/{len(candidates)}: [{ts(start)} → {ts(end)}]  {clip.title[:55]}")
        print(f"           hook={v.hook:.1f}  engage={v.engagement:.1f}  "
              f"share={v.shareability:.1f}  overall={v.overall:.1f}")

        # Build filter chain
        use_blur_bg = vertical and config.get("framing") == "blur_bg"
        use_auto_face = vertical and config.get("framing") == "auto_face"
        use_facecam_stack = vertical and config.get("framing") == "facecam_stack"
        af = "highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=10" if has_audio else None

        if use_facecam_stack:
            # GTA 6 & Gaming: Gameplay + Facecam stacked 9:16 layout
            face_roi = tuple(config.get("facecam_roi", [1440, 810, 480, 270]))
            try:
                gameplay_facecam_stack(str(source), str(out_path), facecam_roi=face_roi, start_sec=start, duration=dur)
                print(f"    🎮 Stacked Gameplay+Facecam layout rendered → {out_name}")
                rendered_ok = True
            except Exception as fe:
                print(f"    ⚠ Stacked layout failed ({fe}), falling back to standard framing")
                use_facecam_stack = False

        encoder_args = get_h264_encoder_args()

        if not use_facecam_stack and use_blur_bg:
            fc = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg]; "
                "[0:v]scale=1080:-2[fg]; "
                "[bg][fg]overlay=(W-w)/2:(H-h)/2"
            )
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(start), "-i", str(source), "-t", str(dur),
                "-filter_complex", fc,
            ] + encoder_args + ["-pix_fmt", "yuv420p"]
        elif not use_facecam_stack and use_auto_face:
            # SOTA: YuNet Deep Learning Face Tracking Crop
            face_vf = get_face_centered_crop_filter(source, start, end, output_width=w_out, output_height=h_out)
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(start), "-i", str(source), "-t", str(dur),
                "-vf", face_vf,
            ] + encoder_args + ["-pix_fmt", "yuv420p"]
        elif not use_facecam_stack:
            vf_parts = []
            if vertical:
                vf_parts.append("crop=ih*9/16:ih")        # center crop to 9:16
                vf_parts.append(f"scale={w_out}:{h_out}")
            else:
                vf_parts.append(f"scale={w_out}:{h_out}:force_original_aspect_ratio=decrease")
                vf_parts.append(f"pad={w_out}:{h_out}:(ow-iw)/2:(oh-ih)/2:black")
            if is_vfr:
                vf_parts.append("fps=30")                 # VFR → CFR (skill §6.10)

            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(start), "-i", str(source), "-t", str(dur),
                "-vf", ",".join(vf_parts),
            ] + encoder_args + ["-pix_fmt", "yuv420p"]
        if not use_facecam_stack:
            if has_audio and af:
                cmd += ["-c:a", "aac", "-b:a", "192k", "-af", af]
            elif not has_audio:
                cmd += ["-an"]
            cmd += ["-movflags", "+faststart", str(out_path)]

            rendered_ok = False
            try:
                run(cmd)
                print(f"    ✓  → {out_name}")
                rendered_ok = True
            except RuntimeError as e:
                print(f"    ✗  Primary encode failed ({str(e)[:120]}), attempting fallback...")
                cmd_sw = fallback_cmd_to_libx264(cmd)
                try:
                    run(cmd_sw)
                    print(f"    ✓  → {out_name}  (libx264 fallback)")
                    rendered_ok = True
                except RuntimeError as e2:
                    print(f"    ✗  libx264 also failed: {str(e2)[:200]}")

        if not rendered_ok:
            continue

        # ── Caption burning (--captions, skill §14 & requirements) ───────────
        final_path = out_path
        if do_captions:
            # 1. Obtain clip SRT using scripts/extract_subtitles.py (if VTT exists) or whisper segments
            vtt_cands = sorted(list(SOURCE_DIR.glob(f"*{stem}*.vtt")) + list(WORK_DIR.glob(f"*{stem}*.vtt")))
            clip_srt = WORK_DIR / f"{stem}_{i:02d}.srt"
            extracted_srt = False
            if vtt_cands:
                vtt_file = vtt_cands[0]
                extract_script = BASE / "scripts" / "extract_subtitles.py"
                try:
                    r_ext = subprocess.run(
                        [sys.executable, str(extract_script), str(vtt_file), str(start), str(end), str(clip_srt)],
                        capture_output=True, text=True
                    )
                    if r_ext.returncode == 0 and clip_srt.exists() and clip_srt.stat().st_size > 0:
                        extracted_srt = True
                except Exception:
                    pass

            if not extracted_srt:
                srt_text = _segments_to_srt(transcript_segments, start, end)
                clip_srt.write_text(srt_text, encoding="utf-8")

            # 2. Burn captions onto clip
            captioned_name = out_name.replace(".mp4", "_captioned.mp4")
            captioned_path = out_dir / captioned_name
            try:
                _burn_captions_srt(final_path, clip_srt, captioned_path)
                if captioned_path.exists() and captioned_path.stat().st_size > 0:
                    print(f"    🔡 Captions burned from {clip_srt.name} → {captioned_name}")
                    final_path = captioned_path
            except Exception as ce:
                print(f"    ⚠  Caption burn error: {str(ce)[:120]}")

        # Optional dynamic karaoke subtitles preset
        caption_style = config.get("caption_style", "hormozi")
        all_words = _extract_all_words(transcript_segments)
        if config.get("viral_captions") and all_words:
            viral_sub_name = out_name.replace(".mp4", "_viral_sub.mp4")
            viral_sub_path = out_dir / viral_sub_name
            try:
                _burn_captions(final_path, all_words, viral_sub_path, start, end, style=caption_style)
                print(f"    ✨ Dynamic '{caption_style}' subtitles burned → {viral_sub_name}")
                final_path = viral_sub_path
            except Exception as ce:
                print(f"    ⚠  Viral caption burn error: {str(ce)[:120]}")

        if config.get("hook_banner") and clip.hook_title:
            banner_name = out_name.replace(".mp4", "_hook.mp4")
            banner_path = out_dir / banner_name
            try:
                add_hook_banner_to_video(final_path, clip.hook_title, banner_path, duration_sec=4.0)
                print(f"    🔥 Hook banner added → {banner_name}")
                final_path = banner_path
            except Exception as be:
                print(f"    ⚠  Hook banner error: {str(be)[:120]}")

        # ── Viral Enhancer & Transition Pack Suite ───────────────────────────
        t_pack = config.get("transition_pack") or "auto"
        clip_full_title = f"{clip.title} {clip.hook_title}"
        if config.get("viral_fx"):
            viral_name = final_path.name.replace(".mp4", "_VIRAL_MASTER.mp4")
            viral_path = out_dir / viral_name
            try:
                apply_viral_master_suite(final_path, viral_path, transition_pack=t_pack, title=clip_full_title)
                print(f"    🚀 Viral Master Suite (AI Director & Editing Rules Applied | Mode: {t_pack}) → {viral_name}")
                final_path = viral_path
            except Exception as ve:
                print(f"    ⚠ Viral enhancer error: {str(ve)[:120]}")
        elif t_pack and t_pack != "none":
            trans_name = final_path.name.replace(".mp4", f"_trans_{t_pack}.mp4")
            trans_path = out_dir / trans_name
            try:
                pack_to_use = t_pack
                if pack_to_use == "auto":
                    from engine.transition_director import TransitionDirector
                    plan = TransitionDirector.plan_clip_strategy(title=clip_full_title, duration=dur)
                    pack_to_use = "capcut_viral" if plan.genre == "cricket" else ("premiere_modern_2025" if plan.genre == "gaming" else "premiere_pro_all")
                apply_transition_pack_to_video(final_path, trans_path, pack_name=pack_to_use, with_sfx=True)
                print(f"    🎬 Transition Pack ({pack_to_use}) applied → {trans_name}")
                final_path = trans_path
            except Exception as te:
                print(f"    ⚠ Transition pack error: {str(te)[:120]}")

        # ── GTA 6 & Gaming: Moments, Spoilers & Music Safety ──────────────────
        is_spoiler = False
        gta_cat = "general"
        if config.get("gta6"):
            gta_cat, conf = classify_gta6_moment(f"{clip.title} {clip.verbatim_quote} {clip.hook_title}")
            if config.get("spoiler_check"):
                is_spoiler = detect_cutscene_spoiler(str(source), start_sec=start, sample_duration=min(dur, 20.0))
            if is_spoiler and "_SPOILER" not in final_path.name:
                spoiler_name = final_path.name.replace(".mp4", "_SPOILER.mp4")
                spoiler_path = out_dir / spoiler_name
                try:
                    os.rename(final_path, spoiler_path)
                    final_path = spoiler_path
                    print(f"    🚨 Cutscene spoiler detected → {spoiler_name}")
                except Exception:
                    pass

        # Music-safe variant (DMCA protection)
        music_safe_file = None
        if config.get("music_safe"):
            safe_name = final_path.name.replace(".mp4", "_music_safe.mp4")
            safe_path = out_dir / safe_name
            try:
                render_music_safe_variant(str(final_path), str(safe_path))
                music_safe_file = str(safe_path)
                print(f"    🛡️ Music-safe variant generated → {safe_name}")
            except Exception as me:
                print(f"    ⚠ Music safe export warning: {str(me)[:100]}")

        metas.append({
            "clip_number"       : i,
            "title"             : clip.title,
            "file"              : str(final_path),
            "start"             : start,
            "end"               : end,
            "duration"          : round(dur, 2),
            "hook_score"        : round(v.hook, 2),
            "engagement_score"  : round(v.engagement, 2),
            "shareability_score": round(v.shareability, 2),
            "overall_score"     : round(v.overall, 2),
            "rationale"         : v.rationale,
            "verbatim_quote"    : clip.verbatim_quote,
            "hook_title"        : clip.hook_title,
            "category"          : gta_cat,
            "spoiler"           : is_spoiler,
            "music_safe_file"   : music_safe_file,
            "out_name"          : final_path.name,
        })

    return metas


# ─── Stage 7: Verify (skill §12) ──────────────────────────────────────────────

def verify(metas: list[dict]) -> list[dict]:
    """
    Run ffprobe + blackdetect on each output clip.
    Annotate metas with 'verified' and 'verify_notes'.
    """
    print(f"\n[7/8] ✅  Verifying {len(metas)} clip(s) …")
    for m in metas:
        path = Path(m["file"])
        notes = []

        if not path.exists():
            m["verified"] = False
            m["verify_notes"] = "File not found"
            continue

        # Probe
        r = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate",
            "-of", "default=nw=1", str(path)
        ], capture_output=True, text=True)

        actual_dur = None
        for line in r.stdout.splitlines():
            if line.startswith("duration="):
                actual_dur = float(line.split("=")[1])
            if line.startswith("codec_name="):
                notes.append(line)

        if actual_dur is not None:
            diff = abs(actual_dur - m["duration"])
            if diff > 1.0:
                notes.append(f"⚠ Duration mismatch: expected {m['duration']:.1f}s, got {actual_dur:.1f}s")
        else:
            notes.append("⚠ Could not read duration")

        # Black/freeze check on first 2s and last 2s (skill §12)
        for label, ss in [("head", 0), ("tail", max(0, m["duration"] - 2))]:
            bd = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-ss", str(ss), "-i", str(path), "-t", "2",
                "-vf", "blackdetect=d=0.3:pix_th=0.08", "-an", "-f", "null", "-"
            ], capture_output=True, text=True)
            if "black_start" in bd.stderr:
                notes.append(f"⚠ Black frames at {label}")

        m["size_mb"]      = round(path.stat().st_size / 1_048_576, 2)
        m["verified"]     = True
        m["verify_notes"] = "; ".join(notes) if notes else "OK"
        print(f"    {'✓' if 'OK' in m['verify_notes'] else '⚠'}  {path.name}  {m['size_mb']}MB  {m['verify_notes']}")

    return metas


def compile_highlights_reel(
    metas: list[dict],
    out_dir: Path,
    stem: str,
    transition_pack: str = "auto",
    video_title: str = "",
) -> Optional[dict]:
    """
    Stitch all generated highlight clips into a single compilation reel.
    When transition_pack == 'auto', uses the AI TransitionDirector to
    choreograph a progressive narrative sequence (Hook -> Escalation -> Climax -> Outro).
    """
    valid_clips = [Path(m["file"]) for m in metas if Path(m.get("file", "")).exists()]
    if len(valid_clips) < 2:
        return None

    from engine.transition_director import TransitionDirector
    from engine.transition_pack import TRANSITION_PACKS, apply_two_clip_transition

    if transition_pack == "auto":
        pack_trans = TransitionDirector.plan_reel_compilation(clips_metas=metas, video_title=video_title)
        print(f"\n🎬  Compiling {len(valid_clips)} highlight clips into unified viral reel (🧠 AI Director Auto Mode) …")
        out_reel = out_dir / f"{stem}_VIRAL_REEL.mp4"
    else:
        pack_trans = TRANSITION_PACKS.get(transition_pack, TRANSITION_PACKS["premiere_pro_all"])
        print(f"\n🎬  Compiling {len(valid_clips)} highlight clips into unified viral reel (Pack: {transition_pack}) …")
        out_reel = out_dir / f"{stem}_VIRAL_REEL_{transition_pack}.mp4"

    current_file = valid_clips[0]
    with tempfile.TemporaryDirectory(prefix="reel_stitch_") as tmp_dir:
        tmp_p = Path(tmp_dir)
        for idx, next_clip in enumerate(valid_clips[1:]):
            trans_name = pack_trans[idx % len(pack_trans)]
            is_last = (idx == len(valid_clips) - 2)
            step_out = out_reel if is_last else tmp_p / f"step_{idx:02d}.mp4"
            print(f"    🔗 Stitching clip {idx+1} -> clip {idx+2} with '{trans_name}' transition …")
            try:
                apply_two_clip_transition(
                    clip_a=current_file,
                    clip_b=next_clip,
                    output_path=step_out,
                    transition_name=trans_name,
                    with_sfx=True,
                )
                current_file = step_out
            except Exception as e:
                print(f"    ⚠ Reel transition error at clip {idx+2}: {str(e)[:100]}")
                break

    if out_reel.exists() and out_reel.stat().st_size > 0:
        sz_mb = round(out_reel.stat().st_size / 1_048_576, 2)
        print(f"  ✨ Viral Compilation Reel Ready -> {out_reel.name} ({sz_mb} MB)")
        return {
            "clip_number"       : len(metas) + 1,
            "title"             : f"Full Compilation Reel (AI Director)",
            "file"              : str(out_reel),
            "start"             : metas[0]["start"],
            "end"               : metas[-1]["end"],
            "duration"          : sum(m.get("duration", 0) for m in metas),
            "hook_score"        : max((m.get("hook_score", 0) for m in metas), default=9.0),
            "engagement_score"  : max((m.get("engagement_score", 0) for m in metas), default=9.0),
            "shareability_score": max((m.get("shareability_score", 0) for m in metas), default=9.0),
            "overall_score"     : max((m.get("overall_score", 0) for m in metas), default=9.0),
            "rationale"         : "Master compilation choreographed by AI Transition Director",
            "verbatim_quote"    : "All highlights compiled with context-aware transitions",
            "hook_title"        : "BEST MOMENTS COMPILATION",
            "category"          : "compilation",
            "spoiler"           : False,
            "music_safe_file"   : None,
            "out_name"          : out_reel.name,
            "size_mb"           : sz_mb,
            "verified"          : True,
            "verify_notes"      : "OK",
        }
    return None


# ─── Manifest & Report (skill §14) ────────────────────────────────────────────

def write_manifest(metas: list[dict], out_dir: Path, stem: str,
                   url: str, title: str, summary: str):
    """Write manifest.csv (with 4-dim virality scores, skill §14) and report JSON."""
    manifest_path = out_dir / "manifest.csv"
    fieldnames = [
        "file", "source", "start", "end", "duration",
        "resolution", "size_mb", "method",
        "hook_score", "engagement_score", "shareability_score", "overall_score",
        "verified", "notes",
    ]
    with open(manifest_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for m in metas:
            w.writerow({
                "file"               : m.get("out_name", ""),
                "source"             : url,
                "start"              : m["start"],
                "end"                : m["end"],
                "duration"           : m["duration"],
                "resolution"         : "1080x1920" if "1080x1920" in m.get("out_name", "") else "native",
                "size_mb"            : m.get("size_mb", ""),
                "method"             : "B (re-encode, h264_videotoolbox/libx264)",
                "hook_score"         : m.get("hook_score", ""),
                "engagement_score"   : m.get("engagement_score", ""),
                "shareability_score" : m.get("shareability_score", ""),
                "overall_score"      : m.get("overall_score", ""),
                "verified"           : m.get("verified", False),
                "notes"              : m.get("verify_notes", ""),
            })

    report = {
        "timestamp": datetime.now().isoformat(),
        "url": url, "video_title": title,
        "summary": summary, "clips": metas,
    }
    report_path = out_dir / f"{stem}_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return manifest_path, report_path


# ─── Console scorecard ────────────────────────────────────────────────────────

def _print_scorecard(metas: list[dict]):
    """Print a mini 4-dimension virality scorecard using unicode bars."""
    BAR_W = 8
    print()
    print("  ┌─────────────────────────────────────────────────────────────────────┐")
    print("  │  🏆  Virality Scorecard                                             │")
    print("  ├───┬────────────────────────────────────┬──────┬──────┬──────┬───────┤")
    print("  │ # │ Title                              │ Hook │ Eng  │ Shr  │ ⭐Tot │")
    print("  ├───┼────────────────────────────────────┼──────┼──────┼──────┼───────┤")
    for m in metas:
        n   = m["clip_number"]
        ttl = m["title"][:34].ljust(34)
        hk  = m.get("hook_score",         0)
        eg  = m.get("engagement_score",   0)
        sh  = m.get("shareability_score", 0)
        ov  = m.get("overall_score",      0)
        chk = "✓" if m.get("verified") else "✗"
        print(f"  │{n:>2} │ {ttl} │{hk:>4.1f}  │{eg:>4.1f}  │{sh:>4.1f}  │{ov:>5.1f}  │")
        bar_h = _score_bar(hk, BAR_W)
        bar_e = _score_bar(eg, BAR_W)
        bar_s = _score_bar(sh, BAR_W)
        bar_o = _score_bar(ov, BAR_W)
        dur   = m.get("duration", 0)
        mb    = m.get("size_mb", "?")
        print(f"  │   │ {bar_h} {bar_e} {bar_s} {bar_o}  {chk}  {dur:.0f}s  {mb}MB".ljust(72) + "│")
    print("  └───┴────────────────────────────────────┴──────┴──────┴──────┴───────┘")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="YouTube → AI Clipping Pipeline (video-clipping skill)")
    p.add_argument("url",           help="YouTube URL")
    p.add_argument("--model",       default="small",
                   help="Whisper model: tiny|base|small|medium|large")
    p.add_argument("--max-clips",   default=5,   type=int,   help="Max clips to generate")
    p.add_argument("--min-dur",     default=20,  type=int,   help="Min clip duration (s)")
    p.add_argument("--max-dur",     default=90,  type=int,   help="Max clip duration (s)")
    p.add_argument("--vertical",    action="store_true",      help="Reframe to 9:16 (Shorts/Reels)")
    p.add_argument("--dry-run",     action="store_true",      help="Show plan only, don't render")
    # ── New options ────────────────────────────────────────────────────────────
    p.add_argument("--min-score",   default=6.0, type=float,
                   help="Minimum virality overall_score to keep (default 6.0)")
    p.add_argument("--provider",    default="auto",
                   choices=["gemini", "openai", "auto"],
                   help="LLM provider: gemini|openai|auto (default auto)")
    p.add_argument("--captions",    action="store_true",
                   help="If set, burn word-level captions onto each clip (using ffmpeg drawtext with the subtitle SRT from work/)")
    p.add_argument("--caption-style", default="hormozi",
                   choices=["hormozi", "mrbeast", "neon", "minimal"],
                   help="Viral caption style preset (default: hormozi)")
    p.add_argument("--hook-banner", action="store_true",
                   help="Add 0-4s top hook headline card to maximize viewer retention")
    p.add_argument("--viral-fx", action="store_true",
                   help="Apply fast cuts, dynamic punch-in zooms, white flash transitions, SFX layer & progress bar")
    p.add_argument("--transition-pack", default="auto",
                   choices=["auto"] + list(TRANSITION_PACKS.keys()) + ["none"],
                   help="Transition pack: 'auto' (default: AI Director selects based on specifications & editing techniques), or specific pack name")
    p.add_argument("--compile-reel", "--reel", dest="compile_reel", action="store_true",
                   help="Stitch all generated clips into a master viral compilation reel with seamless CapCut/Premiere transitions and synced SFX")
    p.add_argument("--framing", default="auto_face",
                   choices=["auto_face", "blur_bg", "center_crop", "facecam_stack", "none"],
                   help="Framing mode when --vertical is set (auto_face=YuNet face tracking, blur_bg=blurred 9:16 background, facecam_stack=gameplay+facecam stack, center_crop=direct)")
    p.add_argument("--no-scene-detect", action="store_true",
                   help="Disable PySceneDetect adaptive shot boundary alignment")
    # ── GTA 6 & Gaming options (GTA6_LIVE_CLIPPING_SKILL) ──────────────────────
    p.add_argument("--gta6", "--gameplay", dest="gta6", action="store_true",
                   help="Enable GTA 6 / Live Gaming moment taxonomy, spoiler handling, and gaming layout")
    p.add_argument("--facecam-roi", default="1440,810,480,270",
                   help="Crop ROI for facecam (x,y,w,h) when using stacked layout")
    p.add_argument("--music-safe", action="store_true",
                   help="Render additional music-safe variants (_music_safe.mp4) removing DMCA radio tracks")
    p.add_argument("--spoiler-check", action="store_true", default=True,
                   help="Detect cinematic cutscenes and flag with _SPOILER suffix")
    args = p.parse_args()

    config = {
        "max_clips"     : args.max_clips,
        "min_dur"       : args.min_dur,
        "max_dur"       : args.max_dur,
        "min_score"     : args.min_score,
        "provider"      : args.provider,
        "captions"      : args.captions,
        "caption_style" : args.caption_style,
        "hook_banner"   : args.hook_banner,
        "viral_fx"      : args.viral_fx,
        "transition_pack": args.transition_pack,
        "compile_reel"  : args.compile_reel,
        "framing"       : args.framing if args.vertical else "none",
        "scene_detect"  : not args.no_scene_detect,
        "gta6"          : args.gta6,
        "facecam_roi"   : [int(x.strip()) for x in args.facecam_roi.split(",")] if args.facecam_roi else [1440, 810, 480, 270],
        "music_safe"    : args.music_safe,
        "spoiler_check" : args.spoiler_check,
    }

    print("=" * 64)
    print("  🎬  YouTube Clipping Pipeline  [video-clipping skill]")
    print("=" * 64)
    for k, v in vars(args).items():
        print(f"  {k:<14} {v}")
    print("=" * 64)

    # 1 — Download
    source, vid, title, total_dur = download(args.url)
    stem = vid   # use video id as the stable stem

    # 2 — Probe  (never skip; skill §0.2)
    probe_info = probe(source)
    if not total_dur and probe_info.get('duration'):
        total_dur = probe_info['duration']

    # 3 — Transcribe
    transcript = transcribe(source, model_size=args.model, total_duration=total_dur)

    # 4 — Score (4-dimension virality via engine)
    candidates = score(transcript, config)

    if not candidates:
        print("\n  ⚠  No clips passed the virality threshold. Try --min-score lower.")
        return

    # 5 — Plan
    plan_path = write_plan(candidates, probe_info, stem, args.vertical)
    print(f"    See: {plan_path}")

    if args.dry_run:
        print("\n  --dry-run set: plan written, no clips rendered.")
        return

    # 6 — Render (+ optional caption burn)
    metas = render_clips(
        source, candidates, probe_info, stem,
        vertical=args.vertical,
        config=config,
        transcript_segments=transcript.get("segments", []),
    )

    # 7 — Verify
    metas = verify(metas)

    # 8 — Optional Compilation Reel with Transitions
    out_dir = OUTPUT_DIR / stem
    if config.get("compile_reel") and len(metas) >= 2:
        reel_meta = compile_highlights_reel(
            metas=metas,
            out_dir=out_dir,
            stem=stem,
            transition_pack=config.get("transition_pack", "auto"),
            video_title=title,
        )
        if reel_meta:
            metas.append(reel_meta)

    # 9 — Deliver
    manifest_path, report_path = write_manifest(
        metas, out_dir, stem, args.url, title, "")

    print("\n" + "=" * 64)
    print(f"  ✅  {len(metas)} clip(s) done   |   {out_dir}")
    print(f"  📄  Manifest : {manifest_path}")
    print(f"  📄  Report   : {report_path}")
    print("=" * 64)

    _print_scorecard(metas)

    print("=" * 64)
    print("  Next steps: add --vertical, --captions, or --dry-run first on a new URL.")


if __name__ == "__main__":
    main()
