# ClipForge — Setup & Installation Guide

This guide details how to install and configure ClipForge on macOS, Linux, and Windows.

---

## 📋 System Requirements

- **Python**: 3.10, 3.11, or 3.12
- **FFmpeg**: Version 5.0+ with `libx264` and `aac` support
- **Hardware Acceleration (Optional)**:
  - macOS: Apple VideoToolbox (`h264_videotoolbox`)
  - Linux/Windows: NVIDIA NVENC (`h264_nvenc`) or CPU (`libx264`)
- **Memory**: 8 GB RAM minimum (16 GB recommended)
- **Disk Space**: ~5 GB for dependencies and model weights

---

## ⚡ Quick Setup (macOS / Linux)

Run the included automated setup script:

```bash
chmod +x setup.sh
./setup.sh
```

The script verifies system binaries, creates `.venv`, installs dependencies from `requirements.txt`, and ensures the neural face detection model is ready.

---

## 🛠️ Step-by-Step Manual Installation

### 1. Install System Dependencies

#### macOS
```bash
brew install ffmpeg yt-dlp python@3.11
```

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg
```

#### Windows (WSL2)
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg
```

---

### 2. Configure Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 3. Face Tracking Neural Model

The OpenCV YuNet deep-learning face tracker model (`face_detection_yunet.onnx`, 227 KB) is included in `engine/`. If missing, download it via:

```bash
curl -sL "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" -o "engine/face_detection_yunet.onnx"
```

---

### 4. Optional API Keys Configuration

ClipForge operates completely offline using Whisper for transcription and its local speech-cadence scoring engine. To enable optional cloud LLM scoring:

```bash
cp .env.example .env
# Edit .env and supply GEMINI_API_KEY or OPENAI_API_KEY
```

---

## 🚀 Running the Studio

### Web Studio (Gradio UI)
```bash
python3 start_ui.py
# Opens at http://127.0.0.1:7860
```

### Automated Command-Line Pipeline
```bash
python3 pipeline.py "<YOUTUBE_URL>" \
  --vertical \
  --captions \
  --caption-style mrbeast \
  --hook-banner \
  --viral-fx \
  --compile-reel
```
