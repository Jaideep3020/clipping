#!/usr/bin/env python3
"""
scripts/vod_highlights.py — Long-VOD & Stream Gameplay Highlight Finder
======================================================================
Part of GTA 6 Live & Long-Video Clipping Skill.
Processes 1 to 12+ hour VODs using audio loudness spike analysis vs a trailing baseline,
plus optional Twitch chat spike & keyword analysis (shifted for chat lag).

Usage:
    python scripts/vod_highlights.py <VOD_file> [--top 25] [--pre 20] [--post 25]
                                     [--chat chat.json] [--render] [--vertical]
"""

import argparse
import json
import os
import subprocess
import numpy as np

KW = ["clip", "no way", "wtf", "omg", "lmao", "lol", "pog", "wasted", "busted", "crazy", "insane", "bug", "glitch", "jason", "lucia"]


def audio_db_per_sec(path: str, track: int = 0) -> np.ndarray:
    """Stream audio through ffmpeg pipe in 1-second 16kHz s16le blocks; computes RMS dB per sec."""
    cmd = [
        "ffmpeg", "-v", "error", "-i", path,
        "-map", f"0:a:{track}", "-ac", "1", "-ar", "16000",
        "-f", "s16le", "-"
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out = []
    while True:
        b = p.stdout.read(32000)  # 1 second of 16 kHz mono s16le
        if not b:
            break
        x = np.frombuffer(b[: len(b) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
        out.append(float(np.sqrt(np.mean(x * x))) if len(x) else 0.0)
    p.wait()
    return 20 * np.log10(np.array(out) + 1e-6)


def smooth(x: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return x
    lo = k // 2
    xp = np.pad(x, (lo, k - 1 - lo), mode="edge")
    return np.convolve(xp, np.ones(k) / k, mode="valid")


def trailing_mean(x: np.ndarray, w: int) -> np.ndarray:
    c = np.cumsum(np.insert(x, 0, 0.0))
    idx = np.arange(len(x))
    lo = np.maximum(idx - w, 0)
    cnt = idx - lo
    return np.where(cnt == 0, x, (c[idx] - c[lo]) / np.maximum(cnt, 1))


def robust_z(s: np.ndarray) -> np.ndarray:
    med = np.median(s)
    mad = np.median(np.abs(s - med)) * 1.4826
    scale = max(mad, 0.5 * float(np.std(s)), 1e-3)
    return (s - med) / scale


def load_chat(path: str, n: int, lag: float):
    d = json.load(open(path, encoding="utf-8"))
    comments = d.get("comments", []) if isinstance(d, dict) else d
    cnt, kw = np.zeros(n), np.zeros(n)
    for c in comments:
        t = c.get("content_offset_seconds")
        if t is None:
            continue
        i = int(t - lag)
        if not 0 <= i < n:
            continue
        m = c.get("message")
        body = (m.get("body", "") if isinstance(m, dict) else str(m or "")).lower()
        cnt[i] += 1
        kw[i] += any(k in body for k in KW)
    return cnt, kw


def spike_z(series: np.ndarray, smooth_k: int, base_w: int) -> np.ndarray:
    return robust_z(smooth(series, smooth_k) - trailing_mean(series, base_w))


def pick_peaks(score: np.ndarray, top: int, gap: int):
    s = score.copy()
    out = []
    for _ in range(top):
        i = int(np.argmax(s))
        if s[i] <= 0:
            break
        out.append((i, float(s[i])))
        s[max(0, i - gap): i + gap + 1] = -1e9
    return out


def render_candidate(vod: str, c: dict, vertical: bool, outdir: str, encoder: str):
    name = f"{os.path.splitext(os.path.basename(vod))[0]}_{c['rank']:02d}_{int(c['start'])}-{int(c['end'])}"
    out = os.path.join(outdir, name + (".v.mp4" if vertical else ".mp4"))
    if os.path.exists(out):
        return out
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(c["start"]), "-i", vod,
        "-t", str(c["end"] - c["start"])
    ]
    if vertical:
        fc = (
            "[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            "boxblur=25:5[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "0:a:0?"]
    cmd += [
        "-c:v", encoder, "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out
    ]
    subprocess.run(cmd, check=False)
    return out


def main():
    ap = argparse.ArgumentParser(description="Find highlights in multi-hour gameplay VODs")
    ap.add_argument("vod", help="Path to VOD video file")
    ap.add_argument("--top", type=int, default=25, help="Number of highlights to pick")
    ap.add_argument("--pre", type=int, default=20, help="Pre-roll seconds before peak")
    ap.add_argument("--post", type=int, default=25, help="Post-roll seconds after peak")
    ap.add_argument("--gap", type=int, default=90, help="Min seconds between picked peaks")
    ap.add_argument("--audio-track", type=int, default=0, help="Audio track index")
    ap.add_argument("--chat", help="Path to TwitchDownloaderCLI-style chat JSON")
    ap.add_argument("--chat-lag", type=float, default=8.0, help="Chat reaction lag in seconds")
    ap.add_argument("--w-audio", type=float, default=1.0)
    ap.add_argument("--w-chat", type=float, default=1.0)
    ap.add_argument("--w-kw", type=float, default=0.5)
    ap.add_argument("--out", default="work")
    ap.add_argument("--render", action="store_true", help="Render clips immediately")
    ap.add_argument("--vertical", action="store_true", help="9:16 vertical output")
    ap.add_argument("--encoder", default="h264_videotoolbox")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    print(f"Decoding and analyzing audio energy from: {a.vod} ...")
    db = audio_db_per_sec(a.vod, a.audio_track)
    n = len(db)
    if n == 0:
        raise SystemExit("No audio decoded. Check --audio-track or the file.")

    za = np.clip(spike_z(db, 5, 120), 0, None)
    score = a.w_audio * za
    if a.chat and os.path.exists(a.chat):
        print(f"Loading chat events from: {a.chat} (lag={a.chat_lag}s) ...")
        cnt, kw = load_chat(a.chat, n, a.chat_lag)
        score = score + a.w_chat * np.clip(spike_z(cnt, 10, 120), 0, None) \
                      + a.w_kw * np.clip(spike_z(kw, 10, 120), 0, None)

    cands = []
    for rank, (i, s) in enumerate(pick_peaks(score, a.top, a.gap), 1):
        cands.append({
            "rank": rank,
            "peak": i,
            "score": round(s, 2),
            "start": max(0, i - a.pre),
            "end": min(n, i + a.post),
            "audio_z": round(float(za[i]), 2)
        })
    cands.sort(key=lambda c: c["start"])

    cand_file = os.path.join(a.out, "candidates.json")
    json.dump(cands, open(cand_file, "w"), indent=2)
    print(f"\nFound {len(cands)} highlight peaks (saved to {cand_file}):")
    for c in cands:
        print(f"  #{c['rank']:02d}  {c['start']:>6}s - {c['end']:>6}s  score={c['score']}  audio_z={c['audio_z']}")

    if a.render:
        clips_dir = os.path.join(os.path.dirname(a.out) or ".", "clips")
        os.makedirs(clips_dir, exist_ok=True)
        print(f"\nRendering {len(cands)} clips to {clips_dir} ...")
        for c in cands:
            out_file = render_candidate(a.vod, c, a.vertical, clips_dir, a.encoder)
            print(f"  ✓ Rendered: {out_file}")


if __name__ == "__main__":
    main()
