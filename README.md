# 🎬 ClipForge — SOTA AI Video Clipping & Viral Reach Studio

> A state-of-the-art open-source video clipping and viral growth suite powered by:
> - **OpenCV YuNet Deep Learning** — Real-time neural face detection & active speaker tracking for smart 9:16 vertical auto-cropping (no more cutoff speakers!).
> - **PySceneDetect (`scenedetect`)** — Adaptive camera shot boundary detection so cuts snap to natural camera transitions instead of awkward visual shot slivers.
> - **SupoClip 4D Virality Framework (`FujiwaraChoki/supoclip`)** — 4-Dimension Virality Matrix (Hook, Engagement, Value, Shareability), windowed chunking, boundary snapping, and high-CTR hook titles.
> - **Dynamic Word-by-Word Viral Subtitles** — Real-time animated karaoke captions with active word highlighting in **Alex Hormozi** (neon yellow), **MrBeast** (electric green), and **Neon** (cyan) styles.
> - **Retention Engineering** — 0–4s Top Hook Headline cards, Blurred Background vertical reframing, and Mobile Vocal Punch audio mastering.
> - **ClipForge Web Studio UI** — Full-featured Gradio dark-mode studio with real-time progress tracking, live scorecard tables, and instant video preview.

---

## ⚡ SOTA Open-Source Stack Breakdown

| SOTA Tool | Role in Pipeline | Why It Delivers Better Output |
|---|---|---|
| **OpenCV YuNet (`FaceDetectorYN`)** | Active Speaker Tracking & Auto-Crop | Naive center-crop cuts off side-guests or co-hosts. YuNet is a modern deep-learning face detector (227KB) that tracks the speaker's face across frames with Exponential Moving Average (EMA) smoothing for cinematic vertical camera framing. |
| **PySceneDetect (`AdaptiveDetector`)** | Shot Boundary Alignment | When an LLM cuts on transcript audio, speech often starts 0.5s before/after a camera switch. PySceneDetect finds visual shot cuts and snaps the clip boundary to the nearest visual transition, preventing 0.5-second visual flashes from previous scenes. |
| **Pillow + QuickTime RLE Alpha** | Kinetic Word-by-Word Subtitles | Overcomes standard FFmpeg `libass` compilation limitations by rendering 670+ FPS transparent RGBA typography with active word highlights, drop shadows, and heavy black strokes, compositing losslessly via FFmpeg's native `overlay` filter. |
| **faster-whisper / Whisper** | Word-Level Forced Alignment | Millisecond-accurate word boundaries ensure cuts never slice mid-syllable or mid-breath. |
| **EBU R128 Loudness Normalization** | Mobile Vocal Punch Mastering | Filters out low-frequency rumble below 80Hz and normalizes audio to -14 LUFS (the exact sweet spot for mobile phone speakers on TikTok and Shorts). |

---

## 🎨 Subtitle Style Presets

Choose from 4 proven short-form caption presets:

1. **`hormozi`** (Default):
   - Font: Heavy Bold (`Impact` / `Arial Black`)
   - Active Word: **Vibrant Neon Yellow (`#FFE600`)**
   - Inactive Words: Crisp White (`#FFFFFF`) with thick black stroke
   - Case: Uppercase
2. **`mrbeast`**:
   - Active Word: **Electric Green (`#00FF66`)** with drop shadow
   - Punchy, high-energy gaming/challenge aesthetic
3. **`neon`**:
   - Active Word: **Electric Cyan (`#00F0FF`)**
   - Cyberpunk, tech, and podcast aesthetic
4. **`minimal`**:
   - Translucent dark pill badge behind words
   - Clean, professional aesthetic for educational/business clips

---

## 🖥️ ClipForge Web Studio UI

Launch the local studio interface in your browser:

```bash
python start_ui.py
# Available at http://127.0.0.1:7860
```

### Studio Tabs:
1. **⚡ Auto Clip (SOTA Auto-Framing & Virality)**:
   - Paste any YouTube URL
   - Framing Mode: `auto_face (SOTA YuNet Face-Tracking ⚡)` or `blur_bg (Podcast/Gameplay/Wide)`
   - Subtitle Presets: `hormozi`, `mrbeast`, `neon`, `minimal`
   - Toggle **🔥 Top Hook Headline (0-4s)** to curb scroll-away rate
   - Watch live streaming pipeline logs & visual scorecard ratings (`█████████░ 8.8/10`)
   - Instant video playback of the finished viral short
2. **✂️ Manual & Chapters**:
   - Semantic chapter analysis (2–5 min chunks)
   - Interactive checkbox selection of chapters
   - Automatic English + Chinese bilingual subtitles
   - One-click social copy generator (Xiaohongshu, Douyin/TikTok, YouTube Shorts)
3. **🔇 Jump Cut (Silence Remover)**:
   - Upload any raw footage
   - Customize dB noise threshold and word boundary padding
   - Strip silent gaps and dead air instantly without pitch alteration
4. **⚙️ Settings & System Status**:
   - Live hardware status (Apple VideoToolbox / NVENC, YuNet Face Detector, PySceneDetect)
   - Configure API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`)
   - Cache cleaner for intermediate files

---

## 🚀 CLI Quick Start

```bash
# 1. Full Viral Short (YuNet Face-Tracking + PySceneDetect + Hormozi Captions + Hook Banner)
python pipeline.py "https://youtu.be/VIDEO_ID" \
  --vertical \
  --framing auto_face \
  --captions \
  --caption-style hormozi \
  --hook-banner \
  --min-score 6.5

# 2. Blurred Background Mode (for multi-person podcasts or wide gameplay)
python pipeline.py "https://youtu.be/VIDEO_ID" \
  --vertical \
  --framing blur_bg \
  --captions \
  --caption-style mrbeast

# 3. Dry Run (Inspect virality scorecard and titles before rendering)
python pipeline.py "https://youtu.be/VIDEO_ID" --dry-run

# 4. Standalone Subtitle & Banner Burner on an Existing Video
python scripts/burn_viral_subtitles.py clip.mp4 transcript.json viral_clip.mp4 \
  --style hormozi \
  --hook-banner "THE REAL TRUTH ABOUT AGI"

# 5. Generate Viral Reach Metadata Pack (Titles, Captions, Hashtags)
python scripts/generate_viral_pack.py "Title of Clip" "transcript excerpt or path"
```

---

## 🎮 GTA 6 & Live Stream Studio (Special Option)

Built according to the `GTA6_LIVE_CLIPPING_SKILL` specifications for Grand Theft Auto VI and multi-hour live streams on Twitch, Kick, and YouTube.

### Modes:
1. **Mode A: Long-VOD Highlights Finder (`scripts/vod_highlights.py`)**:
   - Streams 1-second 16kHz audio through an FFmpeg pipe to calculate RMS dB spikes against a trailing 2-minute baseline.
   - Ingests Twitch chat JSON (`TwitchDownloaderCLI` format), computes message velocity and keyword spikes, and shifts reactions backwards by `--chat-lag` (5–12s) to account for viewer delay.
   - De-duplicates and ranks top candidates at least `--gap` seconds apart.
   ```bash
   python scripts/vod_highlights.py vod.mp4 --top 25 --render --vertical --chat chat.json --chat-lag 8
   ```

2. **Mode B: Ongoing Live Stream Auto-Clipper (`scripts/record_rolling.sh` & `scripts/live_clipper.py`)**:
   - **Non-blocking Rolling Capture**: Captures live stream into 10-second MPEG-TS segments with automatic background expiration (`KEEP=45` minutes). Recording CPU usage is near-zero (`-c copy`).
   - **Autonomous Analyzer**: Connects to Twitch IRC (`irc.chat.twitch.tv:6697`), computes live loudness z-scores and chat velocity, and auto-renders clips when virality exceeds the threshold.
   ```bash
   # Terminal 1: Rolling Buffer Capture
   bash scripts/record_rolling.sh streamer_name buffer 45

   # Terminal 2: Live Auto-Clipper & Monitor
   python scripts/live_clipper.py --buffer buffer --vertical --channel streamer_name
   ```

3. **Mode C: Instant Replay Hotkey (`touch clip_now`)**:
   - Hit **"⚡ CLIP THAT RIGHT NOW"** in the Web Studio or run `touch clip_now` in the terminal to force an immediate high-priority clip of the last 30s + post-roll reaction.

4. **Gaming Framing & Safety**:
   - **Stacked 9:16 Layout (`--framing facecam_stack`)**: Crops gameplay to 1080x1344 on top and streamer webcam to 1080x576 on bottom (`[game][cam]vstack`).
   - **DMCA Music Shield (`--music-safe`)**: Removes in-game radio music tracks and masters voice/SFX to -14 LUFS to avoid copyright takedowns.
   - **Cutscene Spoiler Detection**: Detects persistent 2.39:1 letterboxing and flags clips with `_SPOILER` to protect campaign story beats.


---

## 📁 Architecture & File Layout

```
clipping/
├── start_ui.py                ← Launch script for the Gradio Web Studio
├── pipeline.py                ← Automated CLI pipeline with SOTA flags
├── clipper.py                 ← Interactive 6-stage chapter clipper CLI
├── requirements.txt           ← SOTA Dependencies (PySceneDetect, OpenCV, Gradio, Whisper)
├── setup.sh                   ← Automated system probe & weights downloader
│
├── engine/                    ← Core AI & SOTA Computer Vision Engine
│   ├── __init__.py
│   ├── clipper_engine.py      ← SupoClip 4D Virality scoring & windowed chunking
│   ├── gta6_clipping.py       ← GTA 6 Moment taxonomy, facecam stack, spoilers & music safety
│   ├── face_tracker.py        ← SOTA YuNet Neural Face Tracker & Dynamic 9:16 Auto-Cropper
│   ├── scene_detector.py      ← SOTA PySceneDetect Adaptive Shot Cut Alignment
│   ├── viral_subtitles.py     ← Word-by-word dynamic karaoke subtitle engine
│   ├── viral_editor.py        ← Top hook banner, blurred background reframing, vocal punch
│   └── face_detection_yunet.onnx ← YuNet Deep Learning Model Weights (227KB)
│
├── ui/                        ← Web Studio Frontend
│   ├── __init__.py
│   ├── app.py                 ← Gradio Blocks application & backend bridges (5 Tabs)
│   └── style.css              ← Custom dark neon theme
│
├── scripts/                   ← Specialized tools
│   ├── vod_highlights.py      ← Multi-hour VOD highlight finder (audio dB + chat lag)
│   ├── record_rolling.sh      ← Live stream rolling MPEG-TS buffer recorder
│   ├── live_clipper.py        ← Real-time automated live stream clipper & hotkey
│   ├── burn_viral_subtitles.py← Standalone viral subtitle & hook banner tool
│   ├── generate_viral_pack.py ← Multi-platform social copy, hashtags & hook titles
│   ├── download_video.py      ← yt-dlp MP4 + subtitle fetcher
│   ├── analyze_subtitles.py   ← VTT cue parser
│   ├── clip_video.py          ← Method B frame-accurate FFmpeg cutter
│   ├── extract_subtitles.py   ← Clip-window subtitle slicing & re-basing
│   ├── translate_subtitles.py ← Batch EN→ZH translator (20 cues/batch = 95% API reduction)
│   ├── make_bilingual_srt.py  ← Dual-language subtitle merger
│   ├── burn_subtitles.py      ← libass hard-burner with path-escape tempdir trick
│   ├── generate_summary.py    ← Multi-platform social copywriter
│   └── jumpcut.py             ← Silence detection & speech condenser
│
├── source/                    ← Original downloads (never modified or overwritten)
├── work/                      ← Cached transcripts, chapter metadata, and plans
├── output/                    ← Pipeline output clips (with manifest.csv & report.json)
└── youtube-clips/             ← Interactive chapter exports & summaries
```
