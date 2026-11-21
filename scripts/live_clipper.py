#!/usr/bin/env python3
"""
scripts/live_clipper.py — Ongoing Live Stream Auto-Clipper
===========================================================
Part of GTA 6 Live & Long-Video Clipping Skill.

Watches the rolling buffer produced by record_rolling.sh, scores each 10s segment
using audio loudness spike z-scores, optional Twitch chat velocity/keyword spikes
(shifted for chat lag), and optional HUD OCR.
Auto-cuts clips with pre-roll and post-roll.

Manual trigger:
    touch clip_now
forces an immediate high-priority clip of the last N seconds.

Usage:
    python scripts/live_clipper.py --buffer buffer --out clips [--channel NAME] [--vertical]
"""

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import socket
import ssl
import statistics
import subprocess
import tempfile
import threading
import time

SEG = 10  # Duration of each rolling buffer segment in seconds


def log(*args):
    print(time.strftime("[%H:%M:%S]"), *args, flush=True)


def detect_best_encoder() -> str:
    """Detect available hardware accelerated encoder, defaulting to libx264."""
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False
        )
        if "h264_videotoolbox" in res.stdout:
            return "h264_videotoolbox"
        if "h264_nvenc" in res.stdout:
            return "h264_nvenc"
    except Exception:
        pass
    return "libx264"


class Baseline:
    """Sliding baseline tracker for z-score spike detection."""
    def __init__(self, floor: float, n: int = 360):
        self.v = collections.deque(maxlen=n)
        self.floor = floor

    def z(self, x: float) -> float:
        if len(self.v) < 12:
            return 0.0
        stdev = statistics.pstdev(self.v)
        return (x - statistics.fmean(self.v)) / max(stdev, self.floor)

    def add(self, x: float):
        self.v.append(x)


class ChatMonitor(threading.Thread):
    """Anonymous Twitch IRC chat listener tracking message velocity and keyword spikes."""
    def __init__(self, channel: str, keywords: list[str]):
        super().__init__(daemon=True)
        self.channel = channel.lower().lstrip("#")
        self.kw = [k.strip().lower() for k in keywords if k.strip()]
        self.msgs = collections.deque(maxlen=200000)
        self.lock = threading.Lock()

    def run(self):
        while True:
            try:
                raw = socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=30)
                s = ssl.create_default_context().wrap_socket(raw, server_hostname="irc.chat.twitch.tv")
                nick = f"justinfan{int(time.time()) % 90000 + 10000}"
                s.sendall(f"NICK {nick}\r\nJOIN #{self.channel}\r\n".encode())
                s.settimeout(330)
                buf = b""
                log(f"Connected to Twitch chat: #{self.channel}")
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b"\r\n" in buf:
                        line, buf = buf.split(b"\r\n", 1)
                        line = line.decode("utf-8", "ignore")
                        if line.startswith("PING"):
                            s.sendall(b"PONG :tmi.twitch.tv\r\n")
                        elif " PRIVMSG " in line:
                            msg = line.split(" PRIVMSG ", 1)[1].split(" :", 1)[-1].lower()
                            with self.lock:
                                self.msgs.append((time.time(), msg))
            except Exception as e:
                log(f"Chat disconnected ({e}); reconnecting in 5s...")
                time.sleep(5)

    def stats(self, t0: float, t1: float) -> tuple[int, int]:
        n = 0
        kw_hits = 0
        with self.lock:
            for ts, m in self.msgs:
                if t0 <= ts < t1:
                    n += 1
                    kw_hits += any(k in m for k in self.kw)
        return n, kw_hits


def measure_loudness(path: str) -> float | None:
    """Compute integrated loudness in LUFS using FFmpeg ebur128 filter."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
             "ebur128=framelog=quiet", "-f", "null", "-"],
            capture_output=True,
            text=True,
            check=False
        )
        m = re.findall(r"I:\s+(-?[\d.]+)\s+LUFS", r.stderr)
        return float(m[-1]) if m else None
    except Exception:
        return None


def ocr_hits(path: str, roi: tuple[int, int, int, int] | None, words: list[str]) -> int:
    """Sample 1 frame/s from cropped ROI and check for target keywords."""
    if not roi:
        return 0
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return 0

    x, y, w, h = roi
    hits = 0
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-vf",
             f"fps=1,crop={w}:{h}:{x}:{y},scale=iw*2:-1,format=gray", f"{d}/f_%02d.png"],
            check=False
        )
        for fn in sorted(os.listdir(d)):
            try:
                txt = pytesseract.image_to_string(Image.open(os.path.join(d, fn))).upper()
                hits += any(wd in txt for wd in words)
            except Exception:
                pass
    return hits


def list_segments(buf_dir: str) -> list[tuple[float, str]]:
    """Return list of (timestamp, filepath) sorted by wall-clock timestamp."""
    out = []
    for p in sorted(glob.glob(os.path.join(buf_dir, "seg_*.ts"))):
        m = re.search(r"seg_(\d{8}_\d{6})\.ts$", p)
        if m:
            try:
                t = dt.datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").timestamp()
                out.append((t, p))
            except ValueError:
                pass
    return out


def render_clip(a: argparse.Namespace, t0: float, t1: float, score: float, meta: dict) -> list[str]:
    """Concatenate rolling MPEG-TS segments and render clip with accurate in/out points."""
    segs = list_segments(a.buffer)
    pick = []
    for i, (s, p) in enumerate(segs):
        nxt = segs[i + 1][0] if i + 1 < len(segs) else s + SEG * 1.5
        if s < t1 and nxt > t0:
            pick.append((s, p))

    if not pick:
        log(f"Warning: No buffered segments cover {t0:.1f} - {t1:.1f} (buffer window expired?)")
        return []

    stamp = dt.datetime.fromtimestamp(t0).strftime("%Y%m%d_%H%M%S")
    name = f"clip_{stamp}_s{score:.1f}"
    lst = os.path.join(a.out, f".list_{stamp}.txt")
    with open(lst, "w") as f:
        for _, p in pick:
            f.write(f"file '{os.path.abspath(p)}'\n")

    ss = max(0.0, t0 - pick[0][0])
    dur = t1 - t0
    outs = []

    encoder = a.encoder
    enc_opts = ["-c:v", encoder]
    if encoder == "libx264":
        enc_opts += ["-preset", "veryfast", "-crf", "20"]
    elif encoder == "h264_videotoolbox":
        enc_opts += ["-b:v", "6000k"]

    # 1. Master landscape clip
    land_path = os.path.join(a.out, name + ".mp4")
    cmd_land = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", lst,
        "-ss", f"{ss:.2f}", "-t", f"{dur:.2f}"
    ] + enc_opts + [
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", land_path
    ]
    subprocess.run(cmd_land, check=False)
    if os.path.exists(land_path):
        outs.append(land_path)

    # 2. Vertical 9:16 clip (blurred background pad)
    if a.vertical:
        vert_path = os.path.join(a.out, name + ".v.mp4")
        fc = (
            "[0:v]split[a][b];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[b]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )
        cmd_vert = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", lst,
            "-ss", f"{ss:.2f}", "-t", f"{dur:.2f}",
            "-filter_complex", fc, "-map", "[v]", "-map", "0:a?"
        ] + enc_opts + [
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", vert_path
        ]
        subprocess.run(cmd_vert, check=False)
        if os.path.exists(vert_path):
            outs.append(vert_path)

    # Clean temporary concat list
    try:
        os.remove(lst)
    except OSError:
        pass

    # Append to manifest.jsonl
    rec = {
        "files": outs,
        "start": dt.datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
        "duration": round(dur, 1),
        "score": round(score, 2),
        "spoiler": "UNKNOWN_REVIEW",
        **meta
    }
    with open(os.path.join(a.out, "manifest.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")

    log(f"✅ Clip ready: {land_path} (score={score:.1f}, dur={dur:.1f}s)")
    return outs


def main():
    ap = argparse.ArgumentParser(description="Ongoing Live Stream Auto-Clipper")
    ap.add_argument("--buffer", default="buffer", help="Directory with rolling .ts segments")
    ap.add_argument("--out", default="clips", help="Output directory for rendered clips")
    ap.add_argument("--channel", help="Twitch channel for live IRC chat signals")
    ap.add_argument("--keywords", default="clip,clip it,no way,wtf,omg,lmao,lol,pog,wasted,busted,crazy,insane,bug,glitch")
    ap.add_argument("--threshold", type=float, default=3.0, help="Min virality score to trigger clip")
    ap.add_argument("--pre", type=float, default=20, help="Pre-roll seconds before peak")
    ap.add_argument("--post", type=float, default=15, help="Post-roll seconds after peak")
    ap.add_argument("--max-len", type=float, default=90, help="Maximum clip length in seconds")
    ap.add_argument("--merge-gap", type=float, default=10, help="Merge clips occurring within N seconds")
    ap.add_argument("--chat-lag", type=float, default=8, help="Viewer reaction lag in seconds")
    ap.add_argument("--w-audio", type=float, default=1.0, help="Weight for audio loudness spike")
    ap.add_argument("--w-chat", type=float, default=1.0, help="Weight for chat velocity spike")
    ap.add_argument("--w-kw", type=float, default=0.4, help="Weight for chat keyword hits")
    ap.add_argument("--w-ocr", type=float, default=1.5, help="Weight for HUD OCR matches")
    ap.add_argument("--ocr-roi", help="Crop x,y,w,h of HUD text region (e.g. 800,900,320,100)")
    ap.add_argument("--ocr-words", default="WASTED,BUSTED,MISSION PASSED,FAILED")
    ap.add_argument("--vertical", action="store_true", help="Also render vertical 9:16 variant")
    ap.add_argument("--encoder", default="auto", help="Video encoder: auto, h264_videotoolbox, h264_nvenc, libx264")
    ap.add_argument("--trigger-file", default="clip_now", help="Hotkey touch-file for instant clip")
    ap.add_argument("--manual-pre", type=float, default=30, help="Seconds to capture prior to manual trigger")
    ap.add_argument("--backfill", action="store_true", help="Score existing segments already in buffer")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    if a.encoder == "auto":
        a.encoder = detect_best_encoder()

    chat = None
    if a.channel:
        chat = ChatMonitor(a.channel, a.keywords.split(","))
        chat.start()

    roi = tuple(int(v) for v in a.ocr_roi.split(",")) if a.ocr_roi else None
    ocr_words = [w.strip().upper() for w in a.ocr_words.split(",")]
    audio_baseline = Baseline(floor=1.5)
    chat_baseline = Baseline(floor=2.0)

    done_segments = set()
    pending = []
    last_warn = 0.0

    if not a.backfill:
        # Ignore segments older than 2 minutes to prevent initial burst
        done_segments.update(p for s, p in list_segments(a.buffer) if s < time.time() - 120)

    wait_window = (a.chat_lag + SEG) if chat else 2
    render_pool = threading.Semaphore(2)

    log(f"🎮 Live Clipper running | Buffer: {a.buffer} | Encoder: {a.encoder} | Touch '{a.trigger_file}' to clip now")

    def register_candidate(t0: float, t1: float, score: float, meta: dict):
        for p in pending:
            if p["t1"] >= t0 - a.merge_gap and p["t0"] <= t1 + a.merge_gap:
                p["t0"] = min(p["t0"], t0)
                p["t1"] = min(max(p["t1"], t1), p["t0"] + a.max_len)
                p["score"] = max(p["score"], score)
                p["meta"].update(meta)
                return
        pending.append({"t0": t0, "t1": min(t1, t0 + a.max_len), "score": score, "meta": dict(meta)})

    def async_render(p):
        with render_pool:
            try:
                render_clip(a, p["t0"], p["t1"], p["score"], p["meta"])
            except Exception as e:
                log(f"Render error: {e}")

    try:
        while True:
            now = time.time()
            segs = list_segments(a.buffer)

            if segs and now - segs[-1][0] > 45 and now - last_warn > 60:
                log("⚠️  Warning: No new segment in buffer for 45+ s. Is record_rolling.sh running?")
                last_warn = now

            for i, (s0, p) in enumerate(segs[:-1]):
                s1 = segs[i + 1][0]
                if p in done_segments or now < s1 + wait_window:
                    continue
                done_segments.add(p)

                la = measure_loudness(p)
                za = audio_baseline.z(la) if la is not None else 0.0
                if la is not None:
                    audio_baseline.add(la)

                n_msgs = 0
                kw_hits = 0
                zc = 0.0
                if chat:
                    n_msgs, kw_hits = chat.stats(s0 + a.chat_lag, s1 + a.chat_lag)
                    zc = chat_baseline.z(n_msgs)
                    chat_baseline.add(n_msgs)

                oc = ocr_hits(p, roi, ocr_words) if roi else 0

                score = (
                    a.w_audio * max(za, 0.0) +
                    a.w_chat * max(zc, 0.0) +
                    a.w_kw * min(kw_hits, 6) +
                    a.w_ocr * min(oc, 3)
                )

                if score >= a.threshold:
                    log(f"🔥 Live Moment Triggered: score={score:.2f} (audio_z={za:.1f}, chat_z={zc:.1f}, kw={kw_hits})")
                    register_candidate(
                        s0 - a.pre, s1 + a.post, score,
                        {"audio_z": round(za, 2), "chat_msgs": n_msgs, "chat_kw": kw_hits, "ocr_hits": oc}
                    )

            # Check manual trigger file
            if os.path.exists(a.trigger_file):
                try:
                    os.remove(a.trigger_file)
                except OSError:
                    pass
                log("⚡ Manual 'clip_now' hotkey triggered!")
                register_candidate(now - a.manual_pre, now + 5, 99.0, {"manual": True})

            # Check for completed pending windows that are safe to render
            for p in list(pending):
                if now >= p["t1"] + SEG * 1.5 + 2:
                    pending.remove(p)
                    threading.Thread(target=async_render, args=(p,), daemon=True).start()

            time.sleep(2)
    except KeyboardInterrupt:
        log("Live clipper stopped by user.")


if __name__ == "__main__":
    main()
