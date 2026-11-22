# 🎬 ClipForge — Autonomous AI Video Clipping & Viral Reach Studio

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![OpenCV YuNet](https://img.shields.io/badge/face%20tracking-OpenCV%20YuNet%20%2B%20ASD-green.svg)](https://opencv.org/)
[![Whisper](https://img.shields.io/badge/transcription-faster--whisper-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Gemini 2.0 Flash](https://img.shields.io/badge/AI%20Vision-Gemini%202.0%20Multimodal-purple.svg)](https://ai.google.dev/)
[![Meta Demucs](https://img.shields.io/badge/audio-Meta%20Demucs%20Vocal%20Isolation-red.svg)](https://github.com/facebookresearch/demucs)
[![Gradio Studio](https://img.shields.io/badge/UI-Gradio%20Dark%20Studio-yellow.svg)](https://gradio.app/)
[![ECC Integrated](https://img.shields.io/badge/ECC-Agent%20Harness%20Ready-brightgreen.svg)](https://github.com/affaan-m/ecc)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **ClipForge** is a state-of-the-art autonomous video clipping suite that turns multi-hour YouTube videos, podcasts, gaming livestreams, and sports broadcasts into algorithm-optimized 9:16 vertical shorts (TikTok, YouTube Shorts, Instagram Reels) using cutting-edge deep learning and AI models.

---

## 🌟 Key Highlights & SOTA Innovations

- 🧠 **Adaptive AI Editorial Director (`engine/editorial_director.py` & `engine/smart_editor.py`)**: Analyzes footage DNA to auto-classify videos into 6 archetypes (Podcasts, Solo Monologues, Gaming Livestreams, Keynotes, Sports Action, General Content) and dynamically choreographs framing, cut frequency, punch zooms, and typography without manual configuration.
- 🎬 **Autonomous Professional AI Video Editor (`engine/smart_editor.py`)**: Replaces uniform single-transition editing with dynamic, non-repeating transitions (alternating whips, punch zooms, cross zooms, earthquake tremors, analog glitches, optical flashes) choreographing each cut individually like a professional human editor.
- 🎵 **Audio Intelligence & Transient Peak Sync (`engine/audio_beat_sync.py`)**: Fast native RMS energy profiling to detect speech peaks, volume spikes, and excitement onsets—syncing punch zooms and accents to real audio peaks without hardcoded timestamps.
- 🎨 **Cinematic Color Grading Engine (`engine/color_grading.py`)**: Algorithmic Hollywood & short-form color grading presets (Blockbuster Teal & Orange, Hyper Vibrant, Golden Hour, Moody Filmic, Clean Boost) with custom contrast S-curves and subtle focus vignettes.
- 🔊 **Context-Aware Procedural Sound Design (`engine/smart_sfx_designer.py`)**: Synthesizes 48kHz audio effects mapped to specific transition types (whooshes, 808 sub-bass drops at 0-3s hook, glitch chirps, impact thuds) and detected speech transients.
- 🎞️ **Atmospheric Film Overlays (`engine/overlay_effects.py`)**: Subtle 35mm organic film grain to eliminate digital banding, paired with impact RGB chromatic aberration on high-energy cuts.
- 🎯 **Active Speaker Detection (ASD) & OpenCV YuNet (`engine/face_tracker.py`)**: Neural face detection with mouth-movement variance analysis to follow the active speaker across multi-guest podcasts with Exponential Moving Average (EMA) camera smoothing.
- 👁️ **Gemini 2.0 Flash Multimodal Vision (`engine/clipper_engine.py`)**: Ingests compressed video proxies directly into Gemini 2.0 to detect physical stunts, visual comedy, non-verbal hooks, and on-screen action that text-only transcript scoring misses.
- 🎙️ **Meta Demucs Neural Vocal Isolation (`engine/viral_enhancer.py`)**: Two-stem neural audio separation (`htdemucs`) removing copyrighted background tracks, crowd noise, and ambient hum for mobile vocal punch.
- ✂️ **PySceneDetect Adaptive Shot Alignment (`engine/scene_detector.py`)**: Snaps transcript audio cuts to exact camera transitions, preventing jarring 0.5-second visual flashes.
- ✨ **Kinetic Word-by-Word Viral Subtitles (`engine/viral_subtitles.py`)**: Real-time karaoke captions with active word highlighting in **Alex Hormozi** (neon yellow), **MrBeast** (electric green), and **Neon** (cyan) styles.
- 🔥 **Retention Engineering**: 0–4s Top Hook headline banners, blurred background reframing, and mobile-optimized EBU R128 (-14 LUFS) loudness mastering.
- 🎬 **AI Highlights Compilation Reel (`--compile-reel`)**: Stitches individual highlight clips into a narrative compilation reel with cinematic transitions (`whip_left`, `cross_zoom`, `optical_flash`, `additive_dissolve`) and acoustic sound design.
- 🤖 **Everything Claude Code (ECC) Integration**: Fully configured project harness with 60+ domain agents and specialized video editing skills (`video-editing`, `videodb`, `remotion-video-creation`).

---

## 📊 Live Benchmark: Real-World Run

Tested on **Australia v England 2026-27 | First T20I** (`-fBcBdRpLXQ` — 8 min 8 sec 1080p sports broadcast):

```
================================================================
  🎬  YouTube Clipping Pipeline  [video-clipping skill]
================================================================
  [1/8] 📥  Downloading 1080p source video via yt-dlp (139 MB)
  [2/8] 🔍  ffprobe stream analysis & PySceneDetect pass (48,861 frames @ 972 fps)
  [3/8] 🎙️  faster-whisper English word-level forced alignment
  [4/8] 🧠  AI Editorial Director: Identified archetype SPORTS ACTION
  [5/8] 🏆  4D Virality Matrix Scoring: 5 viral moments identified
  [6/8] ✂️  Rendering 9:16 vertical cuts + Hormozi subtitles + 0-4s hook cards
  [7/8] 🎬  Stitching Master Viral Compilation Reel with synced transition SFX
================================================================
```

### 🏆 Output Virality Scorecard

| # | Moment Title | Hook | Eng | Shr | ⭐ Overall | Duration | Resolution | Output File |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **1** | **Six sixes from Harry Brook** | 8.0 | 8.4 | 8.6 | **8.2 / 10** | 89s | 1080x1920 | `..._01_six-sixes-from-harry-brooks-pl_hook_trans_auto.mp4` |
| **2** | **Crazy McGurk** | 8.0 | 8.2 | 8.6 | **8.1 / 10** | 55s | 1080x1920 | `..._02_crazy-mcgurg_hook_trans_auto.mp4` |
| **3** | **Dawson Breaks Through** | 7.1 | 8.8 | 8.1 | **7.9 / 10** | 91s | 1080x1920 | `..._03_dawson-immediately-breaks-thro_hook_trans_auto.mp4` |
| **4** | **First Ball Mitch Marsh** | 7.1 | 8.2 | 8.1 | **7.8 / 10** | 20s | 1080x1920 | `..._04_first-ball-got-him-eventually-_hook_trans_auto.mp4` |
| **5** | **More Home Runs (Baseball Hit)** | 8.0 | 7.6 | 8.1 | **7.8 / 10** | 54s | 1080x1920 | `..._05_six-six-and-thats-more-home-ru_hook_trans_auto.mp4` |
| **⭐** | **Full Master Compilation Reel** | 8.0 | 8.8 | 8.6 | **8.2 / 10** | 309s | 1080x1920 | `..._VIRAL_REEL.mp4` |

---

## ⚡ 1-Click Installation

### Windows (PowerShell)
Run the automated installer to set up `.venv`, verify Python 3.12, check hardware encoders, and download model weights:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### macOS / Linux (Bash)
```bash
chmod +x setup.sh
./setup.sh
```

### Manual Setup
```bash
# 1. Clone repository
git clone https://github.com/Jaideep3020/clipping.git
cd clipping

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure API keys (optional for Gemini / OpenAI scoring)
cp .env.example .env
```

---

## 🖥️ ClipForge Web Studio UI

Launch the dark-mode Gradio studio in your browser:

```bash
python start_ui.py
# Opens at http://127.0.0.1:7860
```

### Studio Features:
1. **⚡ Auto Clip (SOTA Auto-Framing & Virality)**:
   - Paste YouTube URL or upload local video.
   - Choose framing mode (`auto_face` YuNet Face Tracking, `blur_bg`, `facecam_stack`, `center_crop`).
   - Pick subtitle style (`hormozi`, `mrbeast`, `neon`, `minimal`).
   - Enable **🔥 Top Hook Headline (0-4s)** & **🎬 Master Compilation Reel**.
   - Watch real-time streaming progress, live virality scorecard, and video preview.
2. **✂️ Manual & Chapter Clipper**:
   - Semantic chapter analysis (2–5 min chunks) with interactive checkboxes.
   - Bilingual English + Chinese subtitle generation.
   - One-click social copy generator (TikTok, Shorts, Xiaohongshu, Bilibili).
3. **🔇 Jump Cut (Dead Air Remover)**:
   - Strip silent pauses with customizable decibel threshold and padding.
4. **⚙️ System Health & Hardware**:
   - Hardware acceleration status (Apple VideoToolbox / NVENC / CPU).
   - ONNX YuNet model & PySceneDetect checks.

---

## 🚀 CLI Commands & Usage Examples

### 1. Fully Autonomous SOTA Viral Short
```bash
python pipeline.py "https://youtu.be/VIDEO_ID" \
  --vertical \
  --framing auto_face \
  --captions \
  --caption-style hormozi \
  --hook-banner \
  --compile-reel \
  --min-score 6.0
```

### 2. Multi-Guest Podcast with Meta Demucs Vocal Isolation
```bash
python pipeline.py "https://youtu.be/VIDEO_ID" \
  --vertical \
  --framing auto_face \
  --captions \
  --isolate-vocals \
  --min-score 7.0
```

### 3. Visual Stunt / Comedy Video with Gemini 2.0 Multimodal Vision
```bash
python pipeline.py "https://youtu.be/VIDEO_ID" \
  --vertical \
  --multimodal \
  --captions \
  --caption-style mrbeast
```

### 4. Gaming Livestream / GTA 6 Stacked Layout
```bash
python pipeline.py "https://youtu.be/VIDEO_ID" \
  --vertical \
  --framing facecam_stack \
  --facecam-roi "1440,810,480,270" \
  --gta6 \
  --music-safe
```

### 5. Dry Run (Inspect virality scorecard and titles before rendering)
```bash
python pipeline.py "https://youtu.be/VIDEO_ID" --dry-run
```

### 6. Generate Viral Reach Metadata Pack (Titles, Captions, Hashtags)
```bash
python scripts/generate_viral_pack.py "Six sixes from Harry Brook" "transcript excerpt or file path"
```

### 7. Run Standalone Autonomous Pro Editor on Any Existing Clip
Apply dynamic non-repeating transitions, audio-synced pattern interrupt zooms, cinematic color grading, contextual sound design, and 35mm film texture to any existing video:
```bash
python scripts/smart_edit.py clip.mp4 clip_PRO_EDIT.mp4 --color-grade teal_orange
```

---

## 🧬 Adaptive Editorial Director: Content Archetypes

The `AdaptiveEditorialDirector` inspects video frames, audio properties, and transcripts to automatically formulate the optimal editing strategy:

| Content Archetype | Detection Signals | Auto Framing | Pacing & Cuts | Caption Style | Audio & Master |
|---|---|---|---|---|---|
| **Podcast** | Multiple speakers, conversational speech, interview keywords | Active Speaker Detection (ASD) | 45–90s contextual segments | `hormozi` (Yellow highlight) | Meta Demucs vocal isolation + -14 LUFS |
| **Solo Talker** | Single central face, monologue, vlog format | Face-centered crop with punch-in zooms | 30–60s snappy cuts with pattern interrupts | `hormozi` / `neon` | Highpass 80Hz + EBU R128 |
| **Gaming** | HUD/radar elements, high saturation, gameplay keywords | `facecam_stack` (game top, webcam bottom) | Rapid action cuts + transition SFX | `mrbeast` (Electric green) | DMCA music safety filter |
| **Keynote / Presentation** | Slides, 16:9 presentations, low face motion | Blurred background or letterbox preserve | 60–90s complete conceptual ideas | `minimal` (Dark translucent pill) | Clear speech normalization |
| **Sports Action** | High motion variance, field views, crowd roar spikes | Visual boundary snapping + pan | Pacing synced to pivotal moments | `mrbeast` / `hormozi` | Crowd ducking + dynamic punch |
| **General** | Balanced audiovisual profile | Auto-face / Blur background fallback | 30–75s balanced chunks | `hormozi` | Standard mobile mastering |

---

## 🎨 Subtitle Style Presets

| Style | Font & Aesthetics | Active Word Color | Best For |
|---|---|:---:|---|
| **`hormozi`** | Ultra-bold Impact/Arial Black, heavy black outline | **Vibrant Neon Yellow (`#FFE600`)** | Business, advice, motivation, podcasts |
| **`mrbeast`** | Heavy punchy font, deep drop shadow | **Electric Green (`#00FF66`)** | Gaming, challenges, sports, entertainment |
| **`neon`** | Modern bold, cyber glow styling | **Electric Cyan (`#00F0FF`)** | Tech, coding, futuristic topics, night vlogs |
| **`minimal`** | Clean sans-serif with translucent dark pill background | **Soft Yellow (`#FFDC28`)** | Corporate, educational, clean keynote shorts |

---

## 📁 Repository Structure

```
clipping/
├── start_ui.py                ← Gradio Web Studio launcher
├── pipeline.py                ← Automated SOTA CLI pipeline
├── clipper.py                 ← Interactive 6-stage chapter clipper CLI
├── requirements.txt           ← Pinned Python dependencies
├── setup.ps1                  ← 1-click Windows PowerShell installer
├── setup.sh                   ← 1-click macOS/Linux Bash installer
│
├── engine/                    ← Core AI & Computer Vision Engine
│   ├── smart_editor.py        ← Master Autonomous Editor (Choreographs all dynamic post-production)
│   ├── dynamic_transition_engine.py ← Non-Repeating Dynamic Transition Engine (Whips, zooms, glitches, flashes)
│   ├── audio_beat_sync.py     ← Audio intelligence, RMS energy profiling & transient onset detection
│   ├── color_grading.py       ← Cinematic color grading presets (Teal & Orange, Hyper Vibrant, etc.)
│   ├── smart_sfx_designer.py  ← Procedural context-aware sound design & 808 hook impacts
│   ├── overlay_effects.py     ← Atmospheric 35mm film grain & chromatic impact fringe
│   ├── editorial_director.py  ← Adaptive AI Editorial Director (Video DNA archetype routing)
│   ├── clipper_engine.py      ← Gemini 2.0 Multimodal & SupoClip 4D Virality scoring
│   ├── face_tracker.py        ← Active Speaker Detection (ASD) & YuNet 9:16 Face Tracker
│   ├── scene_detector.py      ← PySceneDetect Adaptive Shot Cut Alignment
│   ├── viral_subtitles.py     ← Dynamic word-by-word viral karaoke captions
│   ├── viral_enhancer.py      ← Meta Demucs vocal isolation & synthesized SFX
│   ├── viral_editor.py        ← Top hook banner cards & blurred background reframing
│   ├── transition_director.py ← AI transition sequencing & narrative compilation
│   ├── transition_pack.py     ← Premiere Pro & CapCut transition effects
│   ├── encoder_utils.py       ← Hardware acceleration (VideoToolbox / NVENC / CPU)
│   ├── gta6_clipping.py       ← Gaming layout, facecam stack & spoiler detection
│   └── face_detection_yunet.onnx ← YuNet Deep Learning Weights (227 KB)
│
├── .agents/                   ← Everything Claude Code (ECC) Integration
│   ├── agents/                ← 60+ domain-specific agent definitions
│   ├── rules/                 ← Production engineering, testing & review standards
│   └── skills/                ← Video editing, VideoDB, Remotion, and quality skills
│
├── ui/                        ← Web Studio Frontend
│   ├── app.py                 ← Gradio Blocks application & bridges
│   └── style.css              ← Custom dark neon studio stylesheet
│
├── scripts/                   ← Standalone utility scripts
│   ├── smart_edit.py          ← Standalone Autonomous Professional AI Video Editor
│   ├── generate_viral_pack.py ← AI social copy, titles, hashtags & engagement CTAs
│   ├── burn_viral_subtitles.py← Standalone subtitle & banner burner
│   ├── vod_highlights.py      ← Audio dB + Twitch chat velocity highlight finder
│   ├── live_clipper.py        ← Rolling live stream auto-clipper & hotkey
│   └── jumpcut.py             ← Silence detection & speech condenser
│
├── source/                    ← Downloaded raw media (never modified)
├── work/                      ← Cached transcripts, intermediate plans, and SRTs
├── output/                    ← Finished viral clips, manifests, and compilation reels
└── youtube-clips/             ← Interactive chapter exports
```

---

## 🛠️ Verification & Testing

Run the test suite to verify core engine modules:

```bash
# Verify module imports
python -c "import engine.editorial_director, engine.clipper_engine, engine.face_tracker, engine.viral_subtitles, engine.viral_enhancer; print('All core modules verified!')"

# Test CLI help
python pipeline.py --help
```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
