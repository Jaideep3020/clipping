# 🛠️ ClipForge — Complete Setup & System Dependencies Guide

This document lists all system binaries, Python packages, AI model weights, fonts, and hardware acceleration drivers required to run ClipForge on any machine (macOS, Linux, or Windows).

---

## 📦 1. System-Level Dependencies

Before installing Python packages, ensure the following command-line tools are installed on your host system:

| Binary | Minimum Version | Purpose | Installation Command |
|---|---|---|---|
| **FFmpeg** | `5.0+` (6.x+ recommended) | Video slicing, filtering (`xfade`, `drawtext`, `overlay`), audio mastering | macOS: `brew install ffmpeg`<br>Ubuntu: `sudo apt install ffmpeg`<br>Windows: `winget install Gyan.FFmpeg` |
| **FFprobe** | Bundled with FFmpeg | Media stream probing (resolution, framerate, duration) | Included with FFmpeg |
| **Python** | `3.10` – `3.12` | Runtime environment for pipeline and Web Studio | macOS: `brew install python@3.11`<br>Ubuntu: `sudo apt install python3 python3-venv python3-pip` |
| **yt-dlp** | Latest | Video and audio downloading from YouTube | Installed via pip or `brew install yt-dlp` |
| **Git** | `2.30+` | Cloning repository and managing versions | Pre-installed or via package manager |

### Verifying FFmpeg Filters & Encoders
ClipForge uses modern FFmpeg filters for transitions and kinetic subtitles. Check your FFmpeg build:
```bash
# Verify required filters
ffmpeg -filters 2>/dev/null | grep -E "xfade|acrossfade|overlay|boxblur|drawtext"

# Verify video encoders
ffmpeg -encoders 2>/dev/null | grep -E "libx264|videotoolbox|nvenc"
```

---

## 🐍 2. Python Dependencies (`requirements.txt`)

All Python packages are pinned and managed in `requirements.txt`:

### Core Video & Audio
- `yt-dlp>=2024.1.1` — Video & audio extraction
- `openai-whisper>=20231117` — Word-level speech alignment and transcription
- `faster-whisper>=1.0.0` — Accelerated CTranslate2 Whisper engine
- `torch>=2.0.0` — PyTorch deep learning tensor backend
- `numpy>=1.24.0` — Numerical matrix and audio signal operations

### Computer Vision & Editing
- `opencv-python>=4.8.0` — YuNet neural face detection & frame sampling
- `scenedetect>=0.6.0` — PySceneDetect adaptive shot boundary snapping
- `Pillow>=10.0.0` — High-speed alpha typography for kinetic subtitles

### Web Studio Interface
- `gradio>=5.0.0` — Reactive web interface
- `fastapi>=0.115.0` — High-performance backend routing
- `uvicorn>=0.30.0` — ASGI web server

### AI Scoring (Optional Cloud Providers)
- `google-generativeai>=0.7.0` — Optional Gemini 1.5 Flash virality scoring
- `openai>=1.30.0` — Optional GPT-4o virality scoring
*(ClipForge automatically defaults to its built-in speech-cadence virality scoring engine when offline)*

---

## 🧠 3. AI Models & Neural Weights

| Model | Size | Location | Download / Cache Behavior |
|---|---|---|---|
| **YuNet Face Tracker** | `227 KB` | `engine/face_detection_yunet.onnx` | **Pre-bundled** in this repository. Ready immediately. |
| **OpenAI Whisper (`base`)** | `139 MB` | `~/.cache/whisper/base.pt` | Automatically fetched on first run, or pre-cached offline. |
| **CTranslate2 Whisper (Optional)** | `~145 MB` | `~/.cache/huggingface/hub/` | Automatically cached if `faster-whisper` is selected. |

---

## 🔤 4. System Fonts (Kinetic Subtitles & Hook Banners)

ClipForge renders subtitle cards using PIL/Pillow. It automatically searches standard OS font directories in this priority:

- **macOS**: `/System/Library/Fonts/`, `/Library/Fonts/` (`Helvetica`, `Impact`, `Arial`)
- **Linux**: `/usr/share/fonts/truetype/` (`DejaVuSans-Bold.ttf`, `LiberationSans-Bold.ttf`, `freefont`)
- **Windows**: `C:\Windows\Fonts\` (`arialbd.ttf`, `impact.ttf`)

If a specific font is not present, ClipForge automatically falls back to system bold sans-serif without interrupting video rendering.

---

## ⚡ 5. Hardware Acceleration Support

ClipForge automatically detects your GPU/hardware setup and routes encoding commands accordingly:

- **Apple Silicon (M1 / M2 / M3 / M4)**: Uses `-c:v h264_videotoolbox -b:v 8M` (up to 6x faster than software encoding).
- **NVIDIA GPU (Linux / Windows)**: Uses `-c:v h264_nvenc -preset p5 -cq 21`.
- **Universal CPU Fallback**: Automatically falls back to `-c:v libx264 -preset veryfast -crf 18` if hardware encoders are busy or unsupported.

---

## 🚀 6. Step-by-Step Installation

```bash
# 1. Clone repository
git clone https://github.com/Jaideep3020/clipping.git
cd clipping

# 2. Automated setup (creates .venv & installs dependencies)
chmod +x setup.sh
./setup.sh

# 3. Activate environment
source .venv/bin/activate

# 4. Verify installation
python3 -c "import torch, whisper, cv2, scenedetect, PIL, gradio; print("✅ All dependencies verified!")"

# 5. Launch Studio
python3 start_ui.py
```
