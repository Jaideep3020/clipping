#!/usr/bin/env python3
"""
ui/app.py — ClipForge Web Studio (SupoClip + Video-Clipping Skill)
==================================================================
A modern, dark-themed Gradio web interface for the YouTube clipping tool.
Features:
  Tab 1: Auto Clip (SupoClip 4-Dimension Virality Scoring & Smart Render)
  Tab 2: Manual / Chapter Clip (Interactive semantic chapters + bilingual subs)
  Tab 3: Jump Cut (Silence remover / speech condensing)
  Tab 4: Settings & System Status (API keys, HW acceleration, cache)
"""

import os
import sys
import json
import time
import re
import subprocess
import shutil
from pathlib import Path
from typing import Iterator, Tuple, List, Dict, Any, Optional

import gradio as gr

# Ensure root is in path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from engine.transition_pack import (
    ALL_TRANSITIONS,
    TRANSITION_PACKS,
    apply_two_clip_transition,
    apply_transition_pack_to_video,
    get_transition_info,
)

CSS_PATH = Path(__file__).parent / "style.css"
CUSTOM_CSS = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.exists() else ""


# ─────────────────────────────────────────────────────────────────────────────
# Helper Utilities
# ─────────────────────────────────────────────────────────────────────────────

def get_system_status() -> Dict[str, str]:
    """Inspect local system capabilities."""
    status = {}

    # FFmpeg
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        status["ffmpeg"] = r.stdout.splitlines()[0] if r.returncode == 0 else "Not found"
    except Exception:
        status["ffmpeg"] = "Not found"

    # Encoders
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
        has_vt = "h264_videotoolbox" in r.stdout
        has_nv = "h264_nvenc" in r.stdout
        if has_vt:
            status["encoder"] = "Apple VideoToolbox (Hardware Accelerated ⚡)"
        elif has_nv:
            status["encoder"] = "NVIDIA NVENC (Hardware Accelerated ⚡)"
        else:
            status["encoder"] = "libx264 (Software CPU)"
    except Exception:
        status["encoder"] = "Unknown"

    # Subtitles / libass
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        status["libass"] = "Available (Hard burn supported)" if "subtitles" in r.stdout else "Standard build (Soft-subs fallback)"
    except Exception:
        status["libass"] = "Unknown"

    # Python & yt-dlp
    status["python"] = sys.version.split()[0]
    try:
        r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        status["ytdlp"] = r.stdout.strip()
    except Exception:
        status["ytdlp"] = "Not installed"

    # SOTA Tools
    yunet_model = ROOT_DIR / "engine" / "face_detection_yunet.onnx"
    status["yunet"] = "Active ⚡ (YuNet Deep Learning Face Tracker)" if yunet_model.exists() else "Missing"
    try:
        import scenedetect
        status["scenedetect"] = f"Active ✓ (PySceneDetect v{scenedetect.__version__})"
    except ImportError:
        status["scenedetect"] = "Not installed"

    # Keys
    keys_file = Path.home() / ".clipforge_keys.json"
    cached_gemini = False
    cached_openai = False
    if keys_file.exists():
        try:
            kd = json.loads(keys_file.read_text())
            cached_gemini = bool(kd.get("GEMINI_API_KEY") or kd.get("GOOGLE_API_KEY"))
            cached_openai = bool(kd.get("OPENAI_API_KEY"))
        except Exception:
            pass
    has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or cached_gemini)
    has_openai = bool(os.environ.get("OPENAI_API_KEY") or cached_openai)
    status["gemini_key"] = "Configured ✓" if has_gemini else "Autonomous Offline Mode ⚡ (Zero API Key Needed)"
    status["openai_key"] = "Configured ✓" if has_openai else "Autonomous Offline Mode ⚡"

    return status


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1: Auto Clip (Backend Action)
# ─────────────────────────────────────────────────────────────────────────────

def run_auto_clip(
    url: str,
    whisper_model: str,
    max_clips: int,
    min_dur: int,
    max_dur: int,
    min_score: float,
    provider: str,
    vertical: bool,
    captions: bool,
    caption_style: str,
    hook_banner: bool,
    framing_mode: str,
    viral_fx: bool,
    transition_pack: str,
    compile_reel: bool,
    gta6: bool,
    music_safe: bool,
    dry_run: bool,
    progress=gr.Progress(),
) -> Iterator[Tuple[str, List[List[Any]], Optional[str]]]:
    """Stream execution of pipeline.py and yield real-time updates."""
    if not url.strip():
        yield "Error: Please provide a valid YouTube URL.", [], None
        return

    log_buffer: List[str] = []
    table_data: List[List[Any]] = []
    result_video = None

    def log(msg: str):
        log_buffer.append(msg)
        return "\n".join(log_buffer[-30:])

    progress(0.05, desc="Initializing pipeline...")
    yield log("Starting ClipForge Auto-Clipping Pipeline (SupoClip 4D Virality + Viral Styling)..."), table_data, result_video

    if "facecam_stack" in framing_mode.lower():
        clean_framing = "facecam_stack"
    elif "auto_face" in framing_mode.lower():
        clean_framing = "auto_face"
    elif "blur_bg" in framing_mode.lower():
        clean_framing = "blur_bg"
    else:
        clean_framing = "center_crop"

    cmd = [
        sys.executable,
        str(ROOT_DIR / "pipeline.py"),
        url.strip(),
        "--model", whisper_model,
        "--max-clips", str(int(max_clips)),
        "--min-dur", str(int(min_dur)),
        "--max-dur", str(int(max_dur)),
        "--min-score", str(float(min_score)),
        "--provider", provider,
        "--caption-style", caption_style,
        "--framing", clean_framing,
    ]
    if vertical:
        cmd.append("--vertical")
    if captions:
        cmd.append("--captions")
    if hook_banner:
        cmd.append("--hook-banner")
    if viral_fx:
        cmd.append("--viral-fx")
    if transition_pack and transition_pack != "none":
        cmd.extend(["--transition-pack", transition_pack])
    if compile_reel:
        cmd.append("--compile-reel")
    if gta6:
        cmd.append("--gta6")
    if music_safe:
        cmd.append("--music-safe")
    if dry_run:
        cmd.append("--dry-run")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    clip_count = 0
    for line in iter(process.stdout.readline, ''):
        line_clean = line.strip()
        if not line_clean:
            continue

        log_buffer.append(line_clean)

        # Real-time granular progress tracking
        if "[download]" in line_clean and "%" in line_clean:
            m = re.search(r"(\d+(?:\.\d+)?)%", line_clean)
            if m:
                pct = float(m.group(1))
                p_val = 0.05 + 0.25 * (pct / 100.0)
                details = line_clean.split("|")[1].strip() if "|" in line_clean else ""
                progress(p_val, desc=f"Downloading media: {pct:.1f}% ({details})")
        elif "merging" in line_clean.lower() or "[2/8]" in line_clean or "Probing" in line_clean:
            progress(0.32, desc="Merging streams & probing codecs...")
        elif "[transcribe]" in line_clean and "%" in line_clean:
            m = re.search(r"(\d+(?:\.\d+)?)%", line_clean)
            if m:
                pct = float(m.group(1))
                p_val = 0.35 + 0.25 * (pct / 100.0)
                progress(p_val, desc=f"Transcribing audio with Whisper: {pct:.1f}%")
        elif "[3/8]" in line_clean or "Transcribing" in line_clean:
            progress(0.35, desc=f"Transcribing audio with Whisper ({whisper_model})...")
        elif "[4/8]" in line_clean or "Scoring" in line_clean:
            progress(0.62, desc="Applying SupoClip 4D Virality Analysis...")
        elif "Clip " in line_clean and "/" in line_clean:
            m = re.search(r"Clip (\d+)/(\d+)", line_clean)
            if m:
                c_cur, c_tot = int(m.group(1)), int(m.group(2))
                p_val = 0.70 + 0.22 * (c_cur / max(c_tot, 1))
                progress(p_val, desc=f"Rendering clip {c_cur}/{c_tot} (FFmpeg & Subtitles)...")
        elif "[7/8]" in line_clean or "Verifying" in line_clean:
            progress(0.95, desc="Verifying clips (audio sync & black frames)...")

        # Capture scorecard table lines
        # Example format: [ 8.5/10] ████████░░  ✓  Clip Title  (35.2s  4.8MB)
        if "/10]" in line_clean and ("✓" in line_clean or "⚠" in line_clean):
            parts = line_clean.split()
            table_data.append([
                f"Clip {len(table_data)+1}",
                line_clean,
                "Rendered"
            ])

        yield "\n".join(log_buffer[-30:]), table_data, result_video

    process.wait()
    progress(1.0, desc="Finished!")

    # Find the most recently generated clip
    output_dir = ROOT_DIR / "output"
    recent_clips = sorted(output_dir.rglob("*.mp4"), key=os.path.getmtime, reverse=True)
    if recent_clips:
        result_video = str(recent_clips[0])

    final_msg = f"\nPipeline execution finished with exit code {process.returncode}."
    yield log(final_msg), table_data, result_video


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2: Manual / Chapter Clip (Backend Action)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_chapters_for_ui(url: str, progress=gr.Progress()) -> Tuple[str, gr.CheckboxGroup, str]:
    """Download video & subtitles, then run AI semantic chapter analysis."""
    if not url.strip():
        return "Error: Enter a YouTube URL first.", gr.CheckboxGroup(choices=[]), ""

    progress(0.1, desc="Downloading video & subtitles...")
    r_dl = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "download_video.py"), url.strip(), str(ROOT_DIR / "source")],
        capture_output=True, text=True,
    )
    if r_dl.returncode != 0:
        return f"Download failed: {r_dl.stderr}", gr.CheckboxGroup(choices=[]), ""

    info = json.loads(r_dl.stdout.strip())
    vid_id = info["id"]
    title = info["title"]
    dur = info["duration"]
    vtt = info.get("vtt_path", "")

    progress(0.5, desc="Analyzing chapters with AI...")
    if not vtt or not Path(vtt).exists():
        # Fallback to transcribe
        return f"Downloaded '{title}', but no subtitles found to extract chapters. Use Auto Clip tab instead.", gr.CheckboxGroup(choices=[]), vid_id

    r_sub = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "analyze_subtitles.py"), vtt],
        capture_output=True, text=True,
    )
    if r_sub.returncode != 0:
        return f"Subtitle parse failed: {r_sub.stderr}", gr.CheckboxGroup(choices=[]), vid_id

    sub_data = json.loads(r_sub.stdout)

    # Prompt LLM for chapters
    from engine.clipper_engine import _call_llm
    prompt = f"""You are an expert video editor. Analyze this transcript ({dur:.0f}s total):
{sub_data['timestamped'][:25000]}

Generate 3-8 natural chapters (2-5 minutes each).
Return strictly valid JSON:
{{
  "chapters": [
    {{
      "number": 1,
      "title": "<10-20 word concise title>",
      "start": "<MM:SS>",
      "end": "<MM:SS>",
      "summary": "<1-2 sentence core insight>"
    }}
  ]
}}"""
    try:
        llm_res, _ = _call_llm(prompt)
        chapters = llm_res.get("chapters", [])
    except Exception as e:
        return f"AI Analysis failed: {e}", gr.CheckboxGroup(choices=[]), vid_id

    # Cache chapters in work/
    work_file = ROOT_DIR / "work" / f"{vid_id}_chapters.json"
    work_file.write_text(json.dumps(chapters, indent=2, ensure_ascii=False), encoding="utf-8")

    choices = [
        f"{c['number']}. [{c['start']} - {c['end']}] {c['title']} — {c.get('summary','')}"
        for c in chapters
    ]

    status_md = f"### 🎬 {title}\n- **Duration**: {int(dur//60)}m {int(dur%60)}s\n- **Chapters Found**: {len(chapters)}"
    return status_md, gr.CheckboxGroup(choices=choices, value=[choices[0]] if choices else []), vid_id


def process_selected_chapters_ui(
    vid_id: str,
    selected_chapters: List[str],
    bilingual: bool,
    burn: bool,
    summary: bool,
    progress=gr.Progress(),
) -> Tuple[str, Optional[str], str]:
    """Process selected chapters into clips, subtitles, and summaries."""
    if not vid_id or not selected_chapters:
        return "Please analyze a video and select at least one chapter.", None, ""

    work_file = ROOT_DIR / "work" / f"{vid_id}_chapters.json"
    if not work_file.exists():
        return "Chapter cache not found. Please re-analyze.", None, ""

    chapters = json.loads(work_file.read_text(encoding="utf-8"))
    source_video = ROOT_DIR / "source" / f"{vid_id}.mp4"
    source_vtt = list((ROOT_DIR / "source").glob(f"{vid_id}*.vtt"))
    vtt_path = str(source_vtt[0]) if source_vtt else ""

    out_base = ROOT_DIR / "youtube-clips" / "ui_exports"
    out_base.mkdir(parents=True, exist_ok=True)

    # Parse chosen numbers
    chosen_indices = []
    for s in selected_chapters:
        num = int(s.split(".")[0].strip())
        chosen_indices.append(num - 1)

    logs = []
    preview_video = None
    preview_summary = ""

    for step_i, idx in enumerate(chosen_indices):
        ch = chapters[idx]
        ch_title = re.sub(r'[^\w\s-]', '', ch["title"]).replace(" ", "_")[:50]
        ch_dir = out_base / ch_title
        ch_dir.mkdir(parents=True, exist_ok=True)

        progress((step_i + 0.1) / len(chosen_indices), desc=f"Clipping Chapter {ch['number']}...")
        clip_path = ch_dir / f"{ch_title}_clip.mp4"

        # Clip
        subprocess.run([
            sys.executable, str(ROOT_DIR / "scripts" / "clip_video.py"),
            str(source_video), ch["start"], ch["end"], str(clip_path)
        ], check=True)
        logs.append(f"✓ Clipped: {clip_path.name}")
        preview_video = str(clip_path)

        # Subtitles
        if vtt_path:
            en_srt = ch_dir / f"{ch_title}_en.srt"
            # start/end to secs
            def to_s(t):
                p = t.split(":")
                return int(p[0])*60 + float(p[1]) if len(p)==2 else int(p[0])*3600 + int(p[1])*60 + float(p[2])
            subprocess.run([
                sys.executable, str(ROOT_DIR / "scripts" / "extract_subtitles.py"),
                vtt_path, str(to_s(ch["start"])), str(to_s(ch["end"])), str(en_srt)
            ], check=True)

            sub_to_burn = en_srt
            if bilingual:
                progress((step_i + 0.4) / len(chosen_indices), desc="Translating subtitles...")
                zh_srt = ch_dir / f"{ch_title}_zh.srt"
                subprocess.run([
                    sys.executable, str(ROOT_DIR / "scripts" / "translate_subtitles.py"),
                    str(en_srt), str(zh_srt)
                ])
                bi_srt = ch_dir / f"{ch_title}_bilingual.srt"
                subprocess.run([
                    sys.executable, str(ROOT_DIR / "scripts" / "make_bilingual_srt.py"),
                    str(en_srt), str(zh_srt), str(bi_srt)
                ])
                sub_to_burn = bi_srt
                logs.append("✓ Bilingual subtitles generated")

            if burn and sub_to_burn.exists():
                progress((step_i + 0.7) / len(chosen_indices), desc="Burning subtitles...")
                burned_vid = ch_dir / f"{ch_title}_with_subtitles.mp4"
                subprocess.run([
                    sys.executable, str(ROOT_DIR / "scripts" / "burn_subtitles.py"),
                    str(clip_path), str(sub_to_burn), str(burned_vid)
                ])
                if burned_vid.exists():
                    preview_video = str(burned_vid)
                    logs.append("✓ Hard subtitles burned")

        if summary:
            progress((step_i + 0.9) / len(chosen_indices), desc="Generating social copy...")
            summary_json = ROOT_DIR / "work" / f"{ch_title}_info.json"
            summary_json.write_text(json.dumps({
                "title": ch["title"], "summary": ch.get("summary", ""),
                "keywords": ["AI", "Clip", "Shorts"], "transcript_excerpt": ""
            }))
            summary_md = ch_dir / f"{ch_title}_summary.md"
            subprocess.run([
                sys.executable, str(ROOT_DIR / "scripts" / "generate_summary.py"),
                str(summary_json), str(summary_md)
            ])
            if summary_md.exists():
                preview_summary = summary_md.read_text(encoding="utf-8")
                logs.append("✓ Social copy written")

    return "\n".join(logs), preview_video, preview_summary


# ─────────────────────────────────────────────────────────────────────────────
# Tab 3: Jump Cut (Silence Remover)
# ─────────────────────────────────────────────────────────────────────────────

def run_jumpcut_ui(
    video_file,
    noise_db: int,
    min_silence: float,
    padding: float,
    progress=gr.Progress(),
) -> Tuple[str, Optional[str]]:
    """Run jumpcut.py silence removal on an uploaded video."""
    if not video_file:
        return "Please upload a video file first.", None

    progress(0.2, desc="Analyzing audio for silences...")
    in_path = video_file if isinstance(video_file, str) else video_file.name
    out_dir = ROOT_DIR / "output" / "jumpcut"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"jumpcut_{Path(in_path).stem}.mp4"

    cmd = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "jumpcut.py"),
        str(in_path),
        str(out_file),
        f"{noise_db}dB",
        str(min_silence),
        str(padding),
    ]

    progress(0.5, desc="Splicing video and removing dead air...")
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0:
        return f"Jumpcut failed: {r.stderr}", None

    progress(1.0, desc="Done!")
    return r.stdout, str(out_file)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 4: GTA 6 & Live Stream Studio Handlers
# ─────────────────────────────────────────────────────────────────────────────

def run_vod_highlights_ui(
    vod_path: str,
    top_peaks: int,
    pre_s: int,
    post_s: int,
    min_gap: int,
    w_audio: float,
    w_chat: float,
    w_kw: float,
    chat_file: str,
    chat_lag: float,
    render_clips: bool,
    vertical: bool,
    progress=gr.Progress(),
) -> Iterator[Tuple[str, List[List[Any]], Optional[str]]]:
    if not vod_path.strip():
        yield "Error: Please specify a VOD file path or YouTube URL.", [], None
        return

    progress(0.05, desc="Initializing VOD highlight scan...")
    log_lines = ["Starting Long-VOD Highlight Finder (Audio dB Spikes + Chat Reaction Signals)..."]
    table_data = []
    preview_vid = None

    actual_input = vod_path.strip()
    if actual_input.startswith("http://") or actual_input.startswith("https://"):
        progress(0.15, desc="Downloading stream with yt-dlp...")
        log_lines.append(f"Downloading stream: {actual_input}")
        yield "\n".join(log_lines), table_data, preview_vid
        
        dl_dir = ROOT_DIR / "downloads"
        dl_dir.mkdir(exist_ok=True)
        dl_cmd = ["yt-dlp", "-f", "bv*+ba/b", "-o", str(dl_dir / "%(id)s.%(ext)s"), actual_input]
        subprocess.run(dl_cmd, check=False)
        cands = list(dl_dir.glob("*.*"))
        if cands:
            actual_input = str(sorted(cands, key=os.path.getmtime, reverse=True)[0])
            log_lines.append(f"Ingested VOD: {actual_input}")

    cmd = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "vod_highlights.py"),
        actual_input,
        "--top", str(int(top_peaks)),
        "--pre", str(int(pre_s)),
        "--post", str(int(post_s)),
        "--gap", str(int(min_gap)),
        "--w-audio", str(float(w_audio)),
        "--w-chat", str(float(w_chat)),
        "--w-kw", str(float(w_kw)),
        "--chat-lag", str(float(chat_lag)),
    ]
    if chat_file and chat_file.strip() and os.path.exists(chat_file.strip()):
        cmd += ["--chat", chat_file.strip()]
    if render_clips:
        cmd.append("--render")
    if vertical:
        cmd.append("--vertical")

    progress(0.35, desc="Streaming 16kHz audio & computing trailing z-scores...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in iter(proc.stdout.readline, ''):
        l = line.strip()
        if not l:
            continue
        log_lines.append(l)
        if l.startswith("#"):
            # Candidate format: #01    120s -    165s  score=5.42  audio_z=4.12
            parts = l.split()
            if len(parts) >= 6:
                table_data.append([parts[0], f"{parts[1]} {parts[2]} {parts[3]}", parts[4], parts[5]])
        yield "\n".join(log_lines[-25:]), table_data, preview_vid

    proc.wait()
    progress(1.0, desc="Scan complete!")
    
    clips_dir = ROOT_DIR / "clips"
    if clips_dir.exists():
        recent = sorted(clips_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if recent:
            preview_vid = str(recent[0])

    log_lines.append(f"\nVOD Highlight processing complete with exit code {proc.returncode}.")
    yield "\n".join(log_lines[-25:]), table_data, preview_vid


def trigger_clip_now_ui() -> str:
    """Create clip_now trigger file for ongoing live clipper hotkey."""
    p = ROOT_DIR / "clip_now"
    with open(p, "w") as f:
        f.write(str(time.time()))
    return f"⚡ [HOTKEY TRIGGERED at {time.strftime('%H:%M:%S')}] 'clip_now' signal dispatched! Live clipper will cut last 30s + reaction immediately."


def run_stacked_facecam_ui(video_path: str, roi_str: str, progress=gr.Progress()) -> Tuple[str, Optional[str]]:
    if not video_path.strip() or not os.path.exists(video_path.strip()):
        return "Error: Video file not found.", None
    progress(0.2, desc="Preparing stacked 9:16 layout...")
    try:
        roi_vals = tuple(int(x.strip()) for x in roi_str.split(","))
    except Exception:
        roi_vals = (1440, 810, 480, 270)
    
    out_dir = ROOT_DIR / "output" / "gaming"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video_path).stem
    out_file = out_dir / f"{stem}_stacked_9x16.mp4"
    
    from engine.gta6_clipping import gameplay_facecam_stack
    progress(0.5, desc="Rendering stacked layout with hardware encoder...")
    try:
        gameplay_facecam_stack(video_path.strip(), str(out_file), facecam_roi=roi_vals)
        progress(1.0, desc="Stacked layout ready!")
        return f"✅ Stacked gameplay + facecam layout rendered successfully:\n{out_file}", str(out_file)
    except Exception as e:
        return f"❌ Rendering error: {e}", None


def run_music_safe_ui(video_path: str, progress=gr.Progress()) -> Tuple[str, Optional[str]]:
    if not video_path.strip() or not os.path.exists(video_path.strip()):
        return "Error: Video file not found.", None
    progress(0.3, desc="Mastering audio and filtering radio tracks...")
    out_dir = ROOT_DIR / "output" / "music_safe"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video_path).stem
    out_file = out_dir / f"{stem}_music_safe.mp4"

    from engine.gta6_clipping import render_music_safe_variant
    try:
        render_music_safe_variant(video_path.strip(), str(out_file))
        progress(1.0, desc="Music-safe export ready!")
        return f"🛡️ Music-safe DMCA shielded video rendered:\n{out_file}\n(Filtered <80Hz mic rumble, -14 LUFS loudness mastering)", str(out_file)
    except Exception as e:
        return f"❌ Music-safe render error: {e}", None


def scan_spoiler_ui(video_path: str, progress=gr.Progress()) -> str:
    if not video_path.strip() or not os.path.exists(video_path.strip()):
        return "Error: Video file not found."
    progress(0.4, desc="Sampling video frames for 2.39:1 letterbox black bars...")
    from engine.gta6_clipping import detect_cutscene_spoiler
    is_spoiler = detect_cutscene_spoiler(video_path.strip(), start_sec=0.0, sample_duration=20.0)
    if is_spoiler:
        return "🚨 SPOILER DETECTED: Persistent cinematic letterboxing (2.39:1 black bars) found! This clip appears to be a story mission cutscene. Suffix '_SPOILER' is recommended."
    else:
        return "✅ NO CUTSCENE DETECTED: Footage appears to be active open-world gameplay or full-screen HUD gameplay."


def run_transition_2clip_ui(
    clip_a: str,
    clip_b: str,
    transition_name: str,
    duration: float,
    with_sfx: bool,
    progress=gr.Progress(),
) -> Tuple[str, Optional[str]]:
    """Apply any CapCut or Premiere Pro transition between two clips with synced SFX."""
    if not clip_a.strip() or not os.path.exists(clip_a.strip()):
        return "❌ Error: Clip A file not found.", None
    if not clip_b.strip() or not os.path.exists(clip_b.strip()):
        return "❌ Error: Clip B file not found.", None

    progress(0.2, desc=f"Synthesizing {transition_name} transition & SFX...")
    out_dir = ROOT_DIR / "output" / "transitions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{Path(clip_a.strip()).stem}_{transition_name}_{Path(clip_b.strip()).stem[:8]}.mp4"

    try:
        apply_two_clip_transition(
            clip_a=Path(clip_a.strip()),
            clip_b=Path(clip_b.strip()),
            output_path=out_file,
            transition_name=transition_name,
            duration_sec=float(duration),
            with_sfx=with_sfx,
        )
        t_info = get_transition_info(transition_name)
        disp = t_info.display_name if t_info else transition_name
        sfx_lbl = t_info.sfx_type if t_info and with_sfx else "None"
        progress(1.0, desc="Transition complete!")
        return (
            f"🎬 Transition Applied Successfully!\n"
            f"• Transition: {disp}\n"
            f"• Duration: {duration:.2f}s\n"
            f"• Synchronized SFX: {sfx_lbl}\n"
            f"• Output: {out_file}",
            str(out_file),
        )
    except Exception as e:
        return f"❌ Transition Error: {e}", None


def run_transition_pack_ui(
    video_path: str,
    pack_name: str,
    with_sfx: bool,
    progress=gr.Progress(),
) -> Tuple[str, Optional[str]]:
    """Apply an entire CapCut / Premiere Pro transition pack across a video's scene cuts."""
    if not video_path.strip() or not os.path.exists(video_path.strip()):
        return "❌ Error: Video file not found.", None

    progress(0.2, desc=f"Detecting camera cuts & building '{pack_name}' filters...")
    out_dir = ROOT_DIR / "output" / "transitions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{Path(video_path.strip()).stem}_pack_{pack_name}.mp4"

    try:
        apply_transition_pack_to_video(
            input_path=Path(video_path.strip()),
            output_path=out_file,
            pack_name=pack_name,
            with_sfx=with_sfx,
        )
        progress(1.0, desc="Pack enhancement complete!")
        return (
            f"✨ Transition Pack Applied Across Shot Cuts!\n"
            f"• Pack: {pack_name.replace('_', ' ').title()}\n"
            f"• SFX Track: {'Synchronized 48kHz spatial SFX' if with_sfx else 'Off'}\n"
            f"• Output: {out_file}",
            str(out_file),
        )
    except Exception as e:
        return f"❌ Pack Application Error: {e}", None



# ─────────────────────────────────────────────────────────────────────────────
# Tab 4: Settings & Keys
# ─────────────────────────────────────────────────────────────────────────────

def save_api_keys(gemini_key: str, openai_key: str) -> str:
    """Persist API keys to environment and ~/.clipforge_keys.json for active & future sessions."""
    saved = []
    keys_file = Path.home() / ".clipforge_keys.json"
    data = {}
    if keys_file.exists():
        try:
            data = json.loads(keys_file.read_text())
        except Exception:
            pass

    if gemini_key.strip():
        os.environ["GEMINI_API_KEY"] = gemini_key.strip()
        os.environ["GOOGLE_API_KEY"] = gemini_key.strip()
        data["GEMINI_API_KEY"] = gemini_key.strip()
        saved.append("Gemini API Key")
    if openai_key.strip():
        os.environ["OPENAI_API_KEY"] = openai_key.strip()
        data["OPENAI_API_KEY"] = openai_key.strip()
        saved.append("OpenAI API Key")

    try:
        keys_file.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

    return f"Successfully saved API keys (active for UI & CLI sessions): {', '.join(saved)}" if saved else "No keys provided."


def clear_system_cache() -> str:
    """Clear work/ and downloads cache."""
    cleared = 0
    for folder in [ROOT_DIR / "work"]:
        for f in folder.glob("*"):
            if f.is_file():
                f.unlink()
                cleared += 1
    return f"Cleared {cleared} cached intermediate files."


# ─────────────────────────────────────────────────────────────────────────────
# Main Gradio Blocks Application
# ─────────────────────────────────────────────────────────────────────────────

def create_app() -> gr.Blocks:
    sys_status = get_system_status()

    with gr.Blocks(title="ClipForge — AI Video Clipping Studio") as app:
        # Header
        with gr.Column(elem_id="app-header"):
            gr.Markdown(
                """
                # 🎬 ClipForge Studio
                **Intelligent AI Video Clipping & Virality Engine**  
                *Inspired by SupoClip · Powered by Gemini, Whisper & FFmpeg*
                """
            )

        with gr.Tabs() as tabs:

            # ─────────────────────────────────────────────────────────────────
            # TAB 1: Auto Clip (SupoClip 4D Virality)
            # ─────────────────────────────────────────────────────────────────
            with gr.Tab("⚡ Auto Clip (SupoClip Virality)", id="tab_auto"):
                with gr.Row():
                    with gr.Column(scale=5):
                        url_input = gr.Textbox(
                            label="YouTube Video URL",
                            placeholder="https://www.youtube.com/watch?v=...",
                            lines=1,
                        )

                        with gr.Row():
                            whisper_model = gr.Dropdown(
                                label="Whisper Model",
                                choices=["tiny", "base", "small", "medium", "large"],
                                value="small",
                                info="small is optimal for CPU/GPU balance",
                            )
                            provider = gr.Dropdown(
                                label="LLM Scoring Provider",
                                choices=["auto", "gemini", "openai"],
                                value="auto",
                                info="Gemini Flash is fast & free; OpenAI as fallback",
                            )

                        with gr.Row():
                            max_clips_slider = gr.Slider(1, 10, value=5, step=1, label="Max Clips")
                            min_score_slider = gr.Slider(0.0, 10.0, value=6.0, step=0.5, label="Min Virality Score")

                        with gr.Row():
                            min_dur_slider = gr.Slider(10, 120, value=20, step=5, label="Min Duration (s)")
                            max_dur_slider = gr.Slider(30, 180, value=90, step=5, label="Max Duration (s)")

                        with gr.Row():
                            vertical_cb = gr.Checkbox(label="📱 9:16 Vertical", value=True)
                            captions_cb = gr.Checkbox(label="✨ Viral Dynamic Subtitles", value=True)
                            hook_banner_cb = gr.Checkbox(label="🔥 Top Hook Headline (0-4s)", value=True)

                        with gr.Row():
                            viral_fx_cb = gr.Checkbox(label="⚡ Viral FX (Zooms + Flash + SFX + Progress Bar)", value=True)
                            gta6_cb = gr.Checkbox(label="🎮 GTA 6 / Gaming Mode", value=False)
                            music_safe_cb = gr.Checkbox(label="🛡️ Music-Safe (DMCA Shield)", value=False)
                            dry_run_cb = gr.Checkbox(label="📋 Dry Run (Plan Only)", value=False)

                        with gr.Row():
                            caption_style_dropdown = gr.Dropdown(
                                label="Viral Subtitle Preset",
                                choices=["hormozi", "mrbeast", "neon", "minimal"],
                                value="hormozi",
                                info="Hormozi (Yellow Highlight) · MrBeast (Neon Green) · Neon (Electric Cyan)",
                            )
                            framing_dropdown = gr.Dropdown(
                                label="Framing Mode",
                                choices=[
                                    "auto_face (SOTA YuNet Face-Tracking ⚡)",
                                    "blur_bg (Podcast/Gameplay/Wide Canvas)",
                                    "facecam_stack (Gaming Gameplay + Facecam)",
                                    "center_crop (Direct Center)",
                                ],
                                value="auto_face (SOTA YuNet Face-Tracking ⚡)",
                                info="auto_face uses YuNet neural face detection; facecam_stack stacks gameplay and webcam",
                            )

                        with gr.Row():
                            transition_pack_dropdown = gr.Dropdown(
                                label="Transition Engine Strategy",
                                choices=["auto"] + list(TRANSITION_PACKS.keys()) + ["none"],
                                value="auto",
                                info="Default 'auto': AI Director automatically detects content genre, pace & applies professional editing rules",
                            )
                            compile_reel_cb = gr.Checkbox(label="🎞️ Stitch Highlights Reel (Transitions & SFX)", value=True)

                        start_btn = gr.Button("🚀 Start Auto-Clipping", variant="primary", size="lg")

                    with gr.Column(scale=7):
                        status_box = gr.Textbox(
                            label="Pipeline Logs & Progress",
                            lines=14,
                            interactive=False,
                        )
                        output_table = gr.Dataframe(
                            headers=["Clip", "Virality Scorecard", "Status"],
                            datatype=["str", "str", "str"],
                            label="Generated Clips & Virality Breakdown",
                        )
                        preview_player = gr.Video(label="Clip Preview", interactive=False)

                start_btn.click(
                    fn=run_auto_clip,
                    inputs=[
                        url_input,
                        whisper_model,
                        max_clips_slider,
                        min_dur_slider,
                        max_dur_slider,
                        min_score_slider,
                        provider,
                        vertical_cb,
                        captions_cb,
                        caption_style_dropdown,
                        hook_banner_cb,
                        framing_dropdown,
                        viral_fx_cb,
                        transition_pack_dropdown,
                        compile_reel_cb,
                        gta6_cb,
                        music_safe_cb,
                        dry_run_cb,
                    ],
                    outputs=[status_box, output_table, preview_player],
                )

            # ─────────────────────────────────────────────────────────────────
            # TAB 2: Manual / Chapter Clipper
            # ─────────────────────────────────────────────────────────────────
            with gr.Tab("✂️ Manual & Chapters", id="tab_chapters"):
                with gr.Row():
                    with gr.Column(scale=5):
                        chap_url = gr.Textbox(label="YouTube Video URL", placeholder="https://youtu.be/...")
                        analyze_btn = gr.Button("🔍 1. Analyze Video & Chapters", variant="secondary")
                        chap_status = gr.Markdown("Enter a URL and click analyze.")
                        stored_vid_id = gr.Textbox(visible=False)

                        chapter_selector = gr.CheckboxGroup(
                            label="Select Chapters to Clip (2-5 min granularity)",
                            choices=[],
                        )

                        with gr.Row():
                            bilingual_cb = gr.Checkbox(label="🌐 Bilingual Subtitles (EN+ZH)", value=True)
                            burn_chap_cb = gr.Checkbox(label="🔥 Burn Subtitles (Hard Subs)", value=True)
                            summary_cb = gr.Checkbox(label="📝 Generate Social Summary", value=True)

                        process_chap_btn = gr.Button("⚡ 2. Clip Selected Chapters", variant="primary", size="lg")

                    with gr.Column(scale=7):
                        chap_logs = gr.Textbox(label="Processing Log", lines=8, interactive=False)
                        chap_video_player = gr.Video(label="Finished Clip Preview")
                        chap_summary_view = gr.Markdown(label="Social Media Copy")

                analyze_btn.click(
                    fn=analyze_chapters_for_ui,
                    inputs=[chap_url],
                    outputs=[chap_status, chapter_selector, stored_vid_id],
                )

                process_chap_btn.click(
                    fn=process_selected_chapters_ui,
                    inputs=[stored_vid_id, chapter_selector, bilingual_cb, burn_chap_cb, summary_cb],
                    outputs=[chap_logs, chap_video_player, chap_summary_view],
                )

            # ─────────────────────────────────────────────────────────────────
            # TAB 3: Jump Cut (Silence Remover)
            # ─────────────────────────────────────────────────────────────────
            with gr.Tab("🔇 Jump Cut", id="tab_jumpcut"):
                gr.Markdown(
                    """
                    ### ⚡ Automatic Speech Condenser & Silence Remover
                    *Uses FFmpeg `silencedetect` filter to cut dead air, pauses, and idle time without changing pitch.*
                    """
                )
                with gr.Row():
                    with gr.Column():
                        upload_vid = gr.Video(label="Upload Video File", sources=["upload"])
                        with gr.Row():
                            noise_slider = gr.Slider(-50, -15, value=-30, step=1, label="Noise Floor (dB)", info="-30 dB is standard quiet room")
                            silence_slider = gr.Slider(0.1, 2.0, value=0.4, step=0.05, label="Min Silence Duration (s)")
                            pad_slider = gr.Slider(0.0, 0.3, value=0.08, step=0.02, label="Word Boundary Padding (s)")
                        jumpcut_btn = gr.Button("✂️ Remove Silences", variant="primary")

                    with gr.Column():
                        jumpcut_log = gr.Textbox(label="Result & Stats", lines=6, interactive=False)
                        jumpcut_player = gr.Video(label="Condensated Video")

                jumpcut_btn.click(
                    fn=run_jumpcut_ui,
                    inputs=[upload_vid, noise_slider, silence_slider, pad_slider],
                    outputs=[jumpcut_log, jumpcut_player],
                )

            # ─────────────────────────────────────────────────────────────────
            # TAB 4: GTA 6 & Live Stream Studio (Mode A, B, C & Gaming Layouts)
            # ─────────────────────────────────────────────────────────────────
            with gr.Tab("🎮 GTA 6 & Live Studio", id="tab_gta6"):
                gr.Markdown(
                    """
                    ### 🌴 Grand Theft Auto VI & Live Stream Highlight Studio
                    *Built for multi-hour gameplay VODs, real-time rolling stream auto-clipping, gameplay+facecam 9:16 vertical stacking, and music-copyright safe routing.*
                    """
                )

                with gr.Accordion("🎯 Mode A: Long-VOD & Stream Highlight Finder (Audio dB Spikes + Chat Lag)", open=True):
                    with gr.Row():
                        with gr.Column(scale=5):
                            vod_url_input = gr.Textbox(
                                label="VOD Source (YouTube URL or Local File Path)",
                                placeholder="https://youtu.be/... or /path/to/vod.mp4",
                            )
                            chat_json_input = gr.Textbox(
                                label="Twitch Chat JSON (Optional)",
                                placeholder="chat.json (TwitchDownloader format)",
                            )
                            with gr.Row():
                                top_peaks_slider = gr.Slider(5, 50, value=25, step=5, label="Top Peaks")
                                min_gap_slider = gr.Slider(30, 180, value=90, step=15, label="Min Peak Gap (s)")
                            with gr.Row():
                                pre_s_slider = gr.Slider(5, 60, value=20, step=5, label="Pre-Roll (s)")
                                post_s_slider = gr.Slider(5, 60, value=25, step=5, label="Post-Roll (s)")
                            with gr.Row():
                                w_audio_slider = gr.Slider(0.0, 3.0, value=1.0, step=0.1, label="Weight: Audio Spike")
                                w_chat_slider = gr.Slider(0.0, 3.0, value=1.0, step=0.1, label="Weight: Chat Velocity")
                                w_kw_slider = gr.Slider(0.0, 3.0, value=0.5, step=0.1, label="Weight: Keywords")
                            with gr.Row():
                                render_vod_cb = gr.Checkbox(label="Render Clips Immediately", value=True)
                                vertical_vod_cb = gr.Checkbox(label="9:16 Vertical Blur-Pad", value=True)

                            scan_vod_btn = gr.Button("🔍 Find & Render VOD Highlights", variant="primary", size="lg")

                        with gr.Column(scale=7):
                            vod_log = gr.Textbox(label="VOD Analysis Log", lines=8, interactive=False)
                            vod_cands_table = gr.Dataframe(
                                headers=["Rank", "Time Window", "Virality Score", "Audio Z-Score"],
                                label="Top Highlight Candidates",
                            )
                            vod_player = gr.Video(label="Rendered Highlight Preview")

                    scan_vod_btn.click(
                        fn=run_vod_highlights_ui,
                        inputs=[
                            vod_url_input, top_peaks_slider, pre_s_slider, post_s_slider, min_gap_slider,
                            w_audio_slider, w_chat_slider, w_kw_slider, chat_json_input, gr.State(8.0),
                            render_vod_cb, vertical_vod_cb
                        ],
                        outputs=[vod_log, vod_cands_table, vod_player],
                    )

                with gr.Accordion("🔴 Mode B & C: Ongoing Live Stream Auto-Clipper & Replay Buffer", open=True):
                    with gr.Row():
                        with gr.Column(scale=6):
                            gr.Markdown(
                                """
                                **Live Rolling Buffer Architecture:**  
                                1. In terminal, launch the rolling buffer recorder:  
                                   `bash scripts/record_rolling.sh <channel_name> buffer 45`  
                                2. Start the automated live clipper:  
                                   `python scripts/live_clipper.py --buffer buffer --vertical`  
                                3. Hit the button below at any moment to instantly trigger a replay capture!
                                """
                            )
                            clip_now_btn = gr.Button("⚡ CLIP THAT RIGHT NOW (Instant Hotkey)", variant="stop", size="lg")
                            clip_now_status = gr.Markdown("Ready to capture live stream moments.")

                            clip_now_btn.click(
                                fn=trigger_clip_now_ui,
                                outputs=[clip_now_status],
                            )

                with gr.Accordion("🛡️ Gaming Layouts, Spoiler Detection & DMCA Music Safety", open=False):
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("#### 📱 Stacked 9:16 Vertical (Gameplay + Facecam)")
                            gameplay_in = gr.Textbox(label="Source Clip Path", placeholder="/path/to/clip.mp4")
                            roi_in = gr.Textbox(label="Facecam ROI (x,y,w,h)", value="1440,810,480,270")
                            stack_btn = gr.Button("🎮 Render Stacked Layout", variant="secondary")
                            stack_status = gr.Textbox(label="Status", lines=3, interactive=False)
                            stack_player = gr.Video(label="Stacked 9:16 Preview")

                            stack_btn.click(
                                fn=run_stacked_facecam_ui,
                                inputs=[gameplay_in, roi_in],
                                outputs=[stack_status, stack_player],
                            )

                        with gr.Column():
                            gr.Markdown("#### 🛡️ DMCA Music-Safe Shield & Spoiler Scan")
                            safety_in = gr.Textbox(label="Source Video Path", placeholder="/path/to/clip.mp4")
                            with gr.Row():
                                safe_btn = gr.Button("🛡️ Generate Music-Safe Variant", variant="secondary")
                                spoiler_btn = gr.Button("🚨 Scan for Story Cutscene", variant="secondary")
                            safe_status = gr.Textbox(label="Safety Report", lines=3, interactive=False)
                            safe_player = gr.Video(label="Music-Safe Preview")

                            safe_btn.click(
                                fn=run_music_safe_ui,
                                inputs=[safety_in],
                                outputs=[safe_status, safe_player],
                            )
                            spoiler_btn.click(
                                fn=scan_spoiler_ui,
                                inputs=[safety_in],
                                outputs=[safe_status],
                            )

            # ─────────────────────────────────────────────────────────────────
            # TAB 5: Transition Studio (CapCut & Premiere Pro)
            # ─────────────────────────────────────────────────────────────────
            with gr.Tab("🎬 Transition Studio (CapCut & Premiere)", id="tab_transitions"):
                gr.Markdown("""
                ### 🎬 CapCut & Premiere Pro Transition Studio
                Apply industry-standard viral transitions (Whip Pans, Punch Zooms, Light Leaks, RGB Glitches, Film Burns, Cross Dissolves)
                with frame-accurate synthesized sound effects (48kHz whooshes, 808 sub-bass drops, clicks, and risers).
                """)
                with gr.Row():
                    with gr.Column(scale=6):
                        gr.Markdown("#### 🔗 Mode 1: Join 2 Clips with Custom Transition")
                        trans_clip_a = gr.Textbox(label="Outgoing Clip A Path", placeholder="/path/to/clip_a.mp4")
                        trans_clip_b = gr.Textbox(label="Incoming Clip B Path", placeholder="/path/to/clip_b.mp4")
                        with gr.Row():
                            transition_picker = gr.Dropdown(
                                label="Choose Transition (28 Transitions)",
                                choices=list(ALL_TRANSITIONS.keys()),
                                value="whip_left",
                                info="Whips, Punch Zooms, Optical Flashes, RGB Glitches, Cross Dissolves, Slices",
                            )
                            trans_dur_slider = gr.Slider(0.10, 1.0, value=0.25, step=0.05, label="Transition Duration (seconds)")
                        trans_sfx_cb = gr.Checkbox(label="🔊 Synchronized Spatial SFX (Whoosh, 808, Glitch)", value=True)
                        apply_2clip_btn = gr.Button("🎬 Render 2-Clip Transition", variant="primary", size="lg")
                        trans_2clip_status = gr.Textbox(label="Execution Log", lines=4, interactive=False)

                    with gr.Column(scale=6):
                        gr.Markdown("#### ⚡ Mode 2: Apply Transition Pack Across Video Cuts")
                        trans_video_in = gr.Textbox(label="Input Video Path", placeholder="/path/to/full_video.mp4")
                        pack_picker = gr.Dropdown(
                            label="Choose Transition Pack",
                            choices=list(TRANSITION_PACKS.keys()),
                            value="premiere_pro_all",
                            info="All 14 packs: premiere_dissolve, premiere_immersive_vr, premiere_iris, premiere_page_peel, premiere_slide, premiere_wipe, premiere_modern_2025, premiere_pro_all, capcut_viral",
                        )
                        pack_sfx_cb = gr.Checkbox(label="🔊 Synchronized SFX Across All Cuts", value=True)
                        apply_pack_btn = gr.Button("⚡ Apply Pack Across Video", variant="primary", size="lg")
                        trans_pack_status = gr.Textbox(label="Execution Log", lines=4, interactive=False)

                with gr.Row():
                    trans_player = gr.Video(label="Transition Output Preview", interactive=False)

                apply_2clip_btn.click(
                    fn=run_transition_2clip_ui,
                    inputs=[trans_clip_a, trans_clip_b, transition_picker, trans_dur_slider, trans_sfx_cb],
                    outputs=[trans_2clip_status, trans_player],
                )
                apply_pack_btn.click(
                    fn=run_transition_pack_ui,
                    inputs=[trans_video_in, pack_picker, pack_sfx_cb],
                    outputs=[trans_pack_status, trans_player],
                )

            # ─────────────────────────────────────────────────────────────────
            # TAB 6: Settings & System Status
            # ─────────────────────────────────────────────────────────────────
            with gr.Tab("⚙️ Settings & Status", id="tab_settings"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 🔑 API Configuration")
                        gemini_in = gr.Textbox(label="Google Gemini API Key", type="password", placeholder="AIzaSy...")
                        openai_in = gr.Textbox(label="OpenAI API Key", type="password", placeholder="sk-...")
                        save_keys_btn = gr.Button("💾 Save API Keys", variant="primary")
                        key_status = gr.Markdown("")

                        save_keys_btn.click(
                            fn=save_api_keys,
                            inputs=[gemini_in, openai_in],
                            outputs=[key_status],
                        )

                        gr.Markdown("### 🧹 Cache Management")
                        clear_btn = gr.Button("Clear Work & Transcripts Cache", variant="stop")
                        clear_status = gr.Markdown("")
                        clear_btn.click(fn=clear_system_cache, outputs=[clear_status])

                    with gr.Column():
                        gr.Markdown("### 🖥️ System Engine Status")
                        gr.Markdown(
                            f"""
                            | Component | Detected Status |
                            |---|---|
                            | **FFmpeg** | `{sys_status['ffmpeg'][:40]}` |
                            | **Video Encoder** | **{sys_status['encoder']}** |
                            | **Face Tracker** | **{sys_status['yunet']}** |
                            | **Shot Detection** | **{sys_status['scenedetect']}** |
                            | **Subtitles Engine** | {sys_status['libass']} |
                            | **Python Version** | `{sys_status['python']}` |
                            | **yt-dlp** | `{sys_status['ytdlp']}` |
                            | **Gemini Key** | {sys_status['gemini_key']} |
                            | **OpenAI Key** | {sys_status['openai_key']} |
                            """
                        )

        # Footer
        gr.Markdown(
            """
            ---
            <div style="text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                ClipForge Studio · Built with FFmpeg & Gradio · Compliant with Video-Clipping & YouTube-Clipper skills
            </div>
            """
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
