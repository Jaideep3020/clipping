#!/usr/bin/env bash
# setup.sh — One-time project setup with SOTA open-source tools
set -e

echo ""
echo "── 🎬  ClipForge SOTA Video Studio Setup ──"
echo ""

# ── 1. Environment check (skill §1) ──────────────────────────────────────────
echo "[1] Checking system binaries …"
ffmpeg -version | head -1
ffprobe -version | head -1
echo "    ✓ FFmpeg + ffprobe present"
echo ""

echo "    Available encoders:"
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "libx264|libx265|videotoolbox|libsvtav1|aac|libopus" || true
echo ""

echo "    Python:  $(python3 --version)"
which yt-dlp && echo "    ✓ yt-dlp present" || echo "    ⚠ yt-dlp missing"
echo ""

# ── 2. Virtual environment ────────────────────────────────────────────────────
echo "[2] Preparing environment …"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "    ✓ Created .venv/"
else
    echo "    ✓ .venv/ already exists"
fi

# ── 3. Install dependencies ───────────────────────────────────────────────────
echo ""
echo "[3] Installing SOTA Open Source Tools (PySceneDetect, OpenCV YuNet, Gradio, Whisper) …"
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "    ✓ Dependencies installed"

# ── 4. Verify SOTA models ─────────────────────────────────────────────────────
echo ""
echo "[4] Checking SOTA Vision Weights …"
if [ -f "engine/face_detection_yunet.onnx" ]; then
    echo "    ✓ YuNet Neural Face Tracker Model (227KB) present"
else
    echo "    Downloading YuNet SOTA face tracker weights …"
    curl -sL "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" -o "engine/face_detection_yunet.onnx"
    echo "    ✓ YuNet downloaded"
fi

# ── 5. Script permissions ──────────────────────────────────────────────────
echo ""
echo "[5] Setting executable permissions on scripts …"
chmod +x scripts/*.py scripts/*.sh 2>/dev/null || true
echo "    ✓ Scripts ready"

# ── 6. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅  ClipForge SOTA Studio Setup Complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  SOTA Tools Configured:"
echo "    • OpenCV YuNet: Neural Active-Speaker Face Tracking (Auto-Crop 9:16)"
echo "    • PySceneDetect: Adaptive Camera & Shot Cut Boundary Snapping"
echo "    • Dynamic Subtitles: Word-Level Karaoke Animations (Hormozi / Beast)"
echo "    • GTA 6 & Live Streaming: Rolling buffer capture & 'clip_now' instant trigger"
echo "    • Gaming Layouts: Stacked Gameplay+Facecam (9:16) & DMCA Music Shield"
echo "    • Gradio Web Studio: Dark-mode visual editor & real-time monitor"
echo ""
echo "  Usage Modes:"
echo "    1. Web Studio UI:     python start_ui.py"
echo "    2. Auto Pipeline:     python pipeline.py 'https://youtu.be/ID' --vertical --captions"
echo "    3. GTA 6 / Gaming:    python pipeline.py 'https://youtu.be/ID' --gta6 --vertical"
echo "    4. Live Stream Mode:  bash scripts/record_rolling.sh <channel> buffer 45"
echo "                          python scripts/live_clipper.py --buffer buffer --vertical"
echo "    5. Chapters CLI:      python clipper.py 'https://youtu.be/ID'"
echo ""
