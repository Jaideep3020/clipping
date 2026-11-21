#!/usr/bin/env python3
"""
start_ui.py — Launch the ClipForge Web Studio
=============================================
Usage:
    python start_ui.py
    python start_ui.py --port 7860 --no-browser
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from ui.app import create_app, CUSTOM_CSS

def main():
    parser = argparse.ArgumentParser(description="Launch ClipForge Studio Web UI")
    parser.add_argument("--port", type=int, default=7860, help="Web server port (default: 7860)")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--share", action="store_true", help="Create public gradio.live link")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args()

    banner = r"""
  ╔══════════════════════════════════════════════════════════════╗
  ║                                                              ║
  ║   🎬  ClipForge Web Studio — Viral Growth & Gaming Suite     ║
  ║                                                              ║
  ║   • SupoClip 4-Dimension Virality Matrix (Hook/Engage/Value) ║
  ║   • Dynamic Word-by-Word Subtitles (Hormozi / Beast / Neon)  ║
  ║   • YuNet Neural Face-Tracking & Camera Cut Snapping         ║
  ║   • GTA 6 & Live Studio (Audio dB Spikes + IRC Chat Lag)     ║
  ║   • Live Rolling Buffer & 'clip_now' Instant Hotkey Trigger  ║
  ║   • Gameplay + Facecam Stack (9:16) & DMCA Music Shield      ║
  ║   • Mobile Vocal Punch Audio Master (-14 LUFS)               ║
  ║   • JumpCut Silence Removal & Semantic Chapters              ║
  ║                                                              ║
  ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"  🚀  Starting local studio on http://{args.host}:{args.port}")
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        print("  🔑  Gemini API Key:  Active ✓")
    elif os.environ.get("OPENAI_API_KEY"):
        print("  🔑  OpenAI API Key:  Active ✓")
    else:
        print("  ⚠   No API key detected in env (configure inside Settings tab)")
    print("")

    app = create_app()
    app.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        inbrowser=not args.no_browser,
        css=CUSTOM_CSS,
    )

if __name__ == "__main__":
    main()
