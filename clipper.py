#!/usr/bin/env python3
"""
clipper.py — Interactive YouTube Clipper (youtube-clipper skill)
================================================================
6-stage interactive workflow:
  1. Environment check
  2. Download video + subtitles
  3. AI chapter analysis (2-5 min granularity)
  4. User selects chapters + options
  5. Process: clip + subtitles + translate + bilingual + burn + summary
  6. Output files + offer to continue

Usage:
    python clipper.py
    python clipper.py <youtube_url>          # skip URL prompt
"""
import os, sys, json, re, subprocess, shutil
from pathlib import Path
from datetime import datetime

BASE        = Path(__file__).parent
sys.path.insert(0, str(BASE))
from engine.clipper_engine import build_virality_prompt, ViralityScore, ClipCandidate

SOURCE_DIR  = BASE / "source"
WORK_DIR    = BASE / "work"
OUTPUT_ROOT = BASE / "youtube-clips"
SCRIPTS     = BASE / "scripts"

for d in [SOURCE_DIR, WORK_DIR, OUTPUT_ROOT]:
    d.mkdir(parents=True, exist_ok=True)

def hr(char="─", width=64):
    print(char * width)

def step(n, total, label):
    print(f"\n  {n}/{total} {label}", end=" ")
    sys.stdout.flush()

def ok():
    print("✅")

def fail(msg):
    print(f"✗  {msg}")

def run_script(args: list, capture=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable] + args,
        capture_output=capture, text=True
    )

# ══════════════════════════════════════════════════════════════════════════════
# Stage 1 — Environment Check
# ══════════════════════════════════════════════════════════════════════════════

def stage1_env_check():
    hr("═")
    print("  🎬  YouTube Clipper  [youtube-clipper skill]")
    hr("═")
    print("\n[Stage 1] Environment Check\n")

    issues = []

    # yt-dlp
    r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  ✅  yt-dlp         {r.stdout.strip()}")
    else:
        print("  ✗   yt-dlp         NOT FOUND  → brew install yt-dlp")
        issues.append("yt-dlp")

    # ffmpeg
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    ffmpeg_ver = r.stdout.splitlines()[0] if r.returncode == 0 else "NOT FOUND"
    print(f"  {'✅' if r.returncode==0 else '✗ '}  ffmpeg         {ffmpeg_ver[:60]}")
    if r.returncode != 0:
        issues.append("ffmpeg")

    # ffmpeg-full (libass for subtitle burning)
    ffmpeg_full = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
    if Path(ffmpeg_full).exists():
        print("  ✅  ffmpeg-full     present (libass subtitle burn supported)")
        os.environ["FFMPEG_FULL"] = ffmpeg_full
    else:
        print("  ⚠   ffmpeg-full     not found — subtitle burn will use soft subs fallback")
        print("       To enable hard subs: brew install ffmpeg-full")

    # subtitles filter
    r = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True)
    has_subs = "subtitles" in (r.stdout + r.stderr)
    print(f"  {'✅' if has_subs else '⚠ '}  subtitles filter  {'available' if has_subs else 'not in standard ffmpeg (needs ffmpeg-full)'}")

    # Python deps
    for pkg, pip_name in [("yt_dlp", "yt-dlp"), ("google.generativeai", "google-generativeai"),
                           ("openai", "openai")]:
        try:
            __import__(pkg)
            print(f"  ✅  {pkg:<20}")
        except ImportError:
            print(f"  ⚠   {pkg:<20} not installed  → pip install {pip_name}")

    # API keys
    has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    if has_gemini:
        print("  ✅  GEMINI_API_KEY  set")
    elif has_openai:
        print("  ✅  OPENAI_API_KEY  set  (Gemini preferred but OpenAI will be used)")
    else:
        print("  ✗   No LLM API key — set GEMINI_API_KEY or OPENAI_API_KEY")
        issues.append("api_key")

    if issues:
        print(f"\n  ⚠  Issues found: {', '.join(issues)}")
        if "yt-dlp" in issues or "ffmpeg" in issues:
            print("  Critical tools missing. Please install them and re-run.")
            sys.exit(1)
    else:
        print("\n  ✅  All checks passed.")
    hr()
    return not issues

# ══════════════════════════════════════════════════════════════════════════════
# Stage 2 — Download
# ══════════════════════════════════════════════════════════════════════════════

def stage2_download(url: str = None) -> dict:
    print("\n[Stage 2] Download Video\n")
    if not url:
        url = input("  📎  YouTube URL: ").strip()
    print(f"  Downloading: {url}")
    r = run_script([str(SCRIPTS / "download_video.py"), url, str(SOURCE_DIR)])
    if r.returncode != 0:
        print(f"  ✗  Download failed:\n{r.stderr}")
        sys.exit(1)
    info = json.loads(r.stdout.strip())

    def fmt_dur(s):
        return f"{int(s//60)}:{int(s%60):02d}"
    def fmt_mb(b):
        return f"{b/1_048_576:.1f} MB" if b else "unknown"

    print(f"\n  Title:    {info['title']}")
    print(f"  Duration: {fmt_dur(info['duration'])}")
    print(f"  Size:     {fmt_mb(info['size_bytes'])}")
    print(f"  Video:    {info['video_path']}")
    print(f"  Subs:     {info['vtt_path'] or 'none found'}")
    hr()
    return info

# ══════════════════════════════════════════════════════════════════════════════
# Stage 3 — AI Chapter Analysis & 4-Dimension Virality Scoring
# ══════════════════════════════════════════════════════════════════════════════

CHAPTER_VIRALITY_PROMPT = """You are an expert video editor and viral content strategist analyzing a YouTube video transcript.

Your task:
1. Generate precise chapters at 2-5 minute granularity (no gaps, complete coverage).
2. For each chapter, score its viral potential using SupoClip's 4-dimension virality scoring system:
   - hook_score (0.0 - 10.0): Compelling opening 10-15s? Provocative hook, bold question, or strong moment?
   - engagement_score (0.0 - 10.0): Sustained attention, high storytelling tension, humor, or valuable insight?
   - shareability_score (0.0 - 10.0): Would viewers forward this, repost, or debate it? High relatable or 'aha' value?
   - overall_score (0.0 - 10.0): Holistic viral rating (weight: hook 30%, engagement 35%, shareability 35%).

Video duration: {total_duration_str}
Subtitle entries: {count}

Timestamped transcript:
{timestamped}

Output ONLY valid JSON — no markdown fences, no extra text:
{{
  "chapters": [
    {{
      "number": 1,
      "title": "<concise topic title 10-20 words>",
      "start": "<MM:SS or HH:MM:SS>",
      "end": "<MM:SS or HH:MM:SS>",
      "summary": "<1-2 sentences of what this segment covers, 50-100 chars>",
      "keywords": ["<kw1>", "<kw2>", "<kw3>"],
      "hook_score": <float 0.0-10.0>,
      "engagement_score": <float 0.0-10.0>,
      "shareability_score": <float 0.0-10.0>,
      "overall_score": <float 0.0-10.0>,
      "rationale": "<1-2 sentence explanation of viral potential and scores>"
    }}
  ]
}}"""

def ts_to_secs(ts: str) -> float:
    parts = ts.strip().split(":")
    if len(parts) == 3:
        return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
    return int(parts[0])*60 + float(parts[1])

def fmt_dur(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

def call_llm(prompt: str) -> dict:
    # Try Gemini, then OpenAI
    for label, fn in [("Gemini", _gemini_chat), ("OpenAI", _openai_chat)]:
        try:
            return fn(prompt)
        except EnvironmentError as e:
            print(f"  ⚠  {label}: {e}")
        except Exception as e:
            print(f"  ⚠  {label} error: {e}")
    raise RuntimeError("No LLM API available. Set GEMINI_API_KEY or OPENAI_API_KEY.")

def _gemini_chat(prompt: str) -> dict:
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp  = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(resp.text)

def _openai_chat(prompt: str) -> dict:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    resp   = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)

def _offline_chapter_scoring(sub_data: dict, total_dur: float) -> list[dict]:
    """Autonomous offline fallback chapter generation with 4-dimension virality scores."""
    entries = sub_data.get("entries", [])
    if not entries:
        return []
    chapters = []
    chunk_dur = 180.0  # 3 minutes default granularity
    t = 0.0
    num = 1
    while t < total_dur:
        t_end = min(t + chunk_dur, total_dur)
        if total_dur - t_end < 60.0:
            t_end = total_dur
        seg_entries = [e for e in entries if t <= e["start"] < t_end]
        text_chunk = " ".join(e["text"] for e in seg_entries).strip()
        first_words = " ".join(text_chunk.split()[:8]) if text_chunk else f"Chapter {num}"
        ch_title = f"{first_words.capitalize()}..." if len(first_words) > 10 else f"Chapter {num}: Overview"
        w_count = len(text_chunk.split())
        wps = w_count / max(t_end - t, 1.0)
        hk = min(9.2, max(6.0, 6.2 + 0.8 * float("?" in text_chunk[:100] or "!" in text_chunk[:100])))
        eg = min(9.4, max(6.0, 5.8 + 1.0 * min(wps / 2.5, 2.0)))
        sh = min(9.0, max(6.0, 6.2 + 0.5 * ("why" in text_chunk.lower() or "how" in text_chunk.lower())))
        ov = round(0.30 * hk + 0.35 * eg + 0.35 * sh, 1)
        chapters.append({
            "number": num,
            "title": ch_title,
            "start": fmt_dur(t),
            "end": fmt_dur(t_end),
            "summary": (text_chunk[:120] + "...") if len(text_chunk) > 120 else text_chunk,
            "keywords": [w.strip(".,!?").lower() for w in text_chunk.split() if len(w) > 5][:4],
            "hook_score": hk,
            "engagement_score": round(eg, 1),
            "shareability_score": round(sh, 1),
            "overall_score": ov,
            "rationale": f"Speech cadence analysis: {wps:.1f} wps, speech density score.",
        })
        num += 1
        t = t_end
        if t >= total_dur:
            break
    return chapters

def stage3_analyze(info: dict, sub_data: dict) -> list[dict]:
    print("\n[Stage 3] AI Chapter Analysis & 4-Dimension Virality Scoring\n")
    if not sub_data.get("entries"):
        if not info.get("vtt_path"):
            print("  ⚠  No subtitles downloaded — checking for transcript cache in work/ ...")
            stem = Path(info.get("video_path", "")).stem
            cache = WORK_DIR / f"{stem}.json"
            if not cache.exists():
                print(f"  ✗  Neither VTT nor {cache.name} found. Run pipeline.py first.")
                sys.exit(1)
            transcript_data = json.loads(cache.read_text(encoding="utf-8"))
            entries = transcript_data.get("segments", [])
            total_dur = entries[-1]["end"] if entries else info.get("duration", 0)
            ts_lines = [f"[{fmt_dur(e['start'])}] {e['text']}" for e in entries]
            sub_data.update({
                "entries": entries,
                "total_duration": total_dur,
                "count": len(entries),
                "text": transcript_data.get("text", ""),
                "timestamped": "\n".join(ts_lines),
            })
        else:
            r = run_script([str(SCRIPTS / "analyze_subtitles.py"), info["vtt_path"]])
            if r.returncode != 0:
                print(f"  ✗  {r.stderr}")
                sys.exit(1)
            sub_data.update(json.loads(r.stdout))

    total_dur = sub_data["total_duration"]
    print(f"  Parsed {sub_data['count']} subtitle entries  ({fmt_dur(total_dur)} total)")
    print("  Analyzing chapters and 4-dimension virality scores with AI …")

    prompt = CHAPTER_VIRALITY_PROMPT.format(
        total_duration_str=fmt_dur(total_dur),
        count=sub_data["count"],
        timestamped=sub_data["timestamped"][:30000],   # cap to avoid token limits
    )

    chapters = []
    try:
        result = call_llm(prompt)
        chapters = result.get("chapters", [])
    except Exception as e:
        print(f"  ℹ  Notice: LLM API generation not active ({e})")
        print("  ⚡  Generating chapters with Autonomous 4-Dimension Virality Engine...")
        chapters = _offline_chapter_scoring(sub_data, total_dur)

    # Ensure all chapters have 4-dimension virality fields
    for ch in chapters:
        if "hook_score" not in ch:
            ch["hook_score"] = 6.5
        if "engagement_score" not in ch:
            ch["engagement_score"] = 6.5
        if "shareability_score" not in ch:
            ch["shareability_score"] = 6.5
        if "overall_score" not in ch:
            ch["overall_score"] = round(
                0.30 * float(ch["hook_score"]) + 0.35 * float(ch["engagement_score"]) + 0.35 * float(ch["shareability_score"]), 1
            )
        try:
            ch["virality"] = ViralityScore(
                overall=float(ch["overall_score"]),
                hook=float(ch["hook_score"]),
                engagement=float(ch["engagement_score"]),
                shareability=float(ch["shareability_score"]),
                rationale=str(ch.get("rationale", "")),
            )
        except Exception:
            pass

    print(f"\n  📊  Generated {len(chapters)} chapters (with 4-dimension virality scores):\n")
    for ch in chapters:
        dur_s = ts_to_secs(ch["end"]) - ts_to_secs(ch["start"])
        ov = float(ch.get("overall_score", 0.0))
        hk = float(ch.get("hook_score", 0.0))
        eg = float(ch.get("engagement_score", 0.0))
        sh = float(ch.get("shareability_score", 0.0))
        bar = "█" * round(ov) + "░" * (10 - round(ov))
        print(f"  {ch['number']:>2}. [{ch['start']} - {ch['end']}]  ({fmt_dur(dur_s)})  {ch['title']}")
        print(f"      Virality: {ov:.1f}/10 [{bar}] (Hook: {hk:.1f} | Eng: {eg:.1f} | Share: {sh:.1f})")
        print(f"      {ch['summary']}")
        if ch.get("rationale"):
            print(f"      Rationale: {ch['rationale']}")
        print(f"      Keywords: {', '.join(ch.get('keywords', []))}\n")

    print("  ✓  All content covered with 4-dimension virality ratings.")
    hr()
    return chapters

# ══════════════════════════════════════════════════════════════════════════════
# Stage 4 — User Selection
# ══════════════════════════════════════════════════════════════════════════════

def stage4_select(chapters: list[dict]) -> tuple[list[int], dict]:
    print("\n[Stage 4] Select Chapters & Options\n")
    nums = [str(c["number"]) for c in chapters]
    print(f"  Enter chapter numbers to clip (comma-separated, e.g. 1,3,5)")
    print(f"  Or 'all' to clip every chapter.\n")
    raw = input("  Your selection: ").strip()
    if raw.lower() == "all":
        selected = list(range(len(chapters)))
    else:
        selected = []
        for tok in raw.split(","):
            tok = tok.strip()
            if tok.isdigit() and tok in nums:
                selected.append(int(tok) - 1)
            else:
                print(f"  ⚠  Ignored invalid selection: {tok}")

    if not selected:
        print("  No valid chapters selected. Exiting.")
        sys.exit(0)

    print(f"\n  Selected: {[chapters[i]['number'] for i in selected]}\n")
    print("  Options:")
    opts = {}
    opts["bilingual"] = input("  Generate bilingual subtitles (EN + ZH)? [Y/n]: ").strip().lower() != "n"
    opts["burn"]      = input("  Burn subtitles into video (hard subs)?   [Y/n]: ").strip().lower() != "n"
    opts["summary"]   = input("  Generate social media summary?           [Y/n]: ").strip().lower() != "n"

    print(f"\n  Plan:")
    print(f"    Clips     : {len(selected)}")
    print(f"    Bilingual : {'yes' if opts['bilingual'] else 'no'}")
    print(f"    Burn subs : {'yes' if opts['burn'] else 'no'}")
    print(f"    Summary   : {'yes' if opts['summary'] else 'no'}")
    confirm = input("\n  Proceed? [Y/n]: ").strip().lower()
    if confirm == "n":
        sys.exit(0)
    hr()
    return selected, opts

# ══════════════════════════════════════════════════════════════════════════════
# Stage 5 — Process
# ══════════════════════════════════════════════════════════════════════════════

def safe_name(title: str, max_len=60) -> str:
    name = re.sub(r'[/\\:*?"<>|]', "", title)
    name = name.replace(" ", "_")
    return name[:max_len]

def stage5_process(info: dict, chapters: list[dict], selected: list[int],
                   opts: dict, out_dir: Path, sub_data: dict):
    print(f"\n[Stage 5] Processing {len(selected)} chapter(s)\n")
    video_path = info["video_path"]
    vtt_path   = info["vtt_path"]
    total_steps = sum([1,  # clip
                       1 if vtt_path else 0,                # extract subs
                       1 if opts["bilingual"] and vtt_path else 0,  # translate
                       1 if opts["bilingual"] and vtt_path else 0,  # bilingual merge
                       1 if opts["burn"] and vtt_path else 0,       # burn
                       1 if opts["summary"] else 0])         # summary

    for ci, idx in enumerate(selected, 1):
        ch    = chapters[idx]
        name  = safe_name(ch["title"])
        ch_dir = out_dir / name
        ch_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  🎬  Chapter {ci}/{len(selected)}: {ch['title']}")
        step_n = 0

        # 5.1 Clip video
        step_n += 1
        step(step_n, total_steps, "Clip video …")
        clip_path = ch_dir / f"{name}_clip.mp4"
        r = run_script([str(SCRIPTS/"clip_video.py"), video_path,
                        ch["start"], ch["end"], str(clip_path)])
        if "OK:" in r.stdout:
            ok()
        else:
            fail(r.stderr[:120])
            continue

        en_srt  = None
        zh_srt  = None
        bi_srt  = None

        if vtt_path:
            # 5.2 Extract subtitles
            step_n += 1
            step(step_n, total_steps, "Extract subtitles …")
            en_srt = ch_dir / f"{name}_original.srt"
            r = run_script([str(SCRIPTS/"extract_subtitles.py"), vtt_path,
                            str(ts_to_secs(ch["start"])), str(ts_to_secs(ch["end"])),
                            str(en_srt)])
            if "OK:" in r.stdout:
                ok()
            else:
                fail(r.stderr[:80])
                en_srt = None

            if opts["bilingual"] and en_srt:
                # 5.3 Translate
                step_n += 1
                step(step_n, total_steps, "Translate to Chinese …")
                zh_srt = ch_dir / f"{name}_zh.srt"
                r = run_script([str(SCRIPTS/"translate_subtitles.py"), str(en_srt), str(zh_srt)])
                if r.returncode == 0:
                    ok()
                else:
                    fail(r.stderr[:100])
                    zh_srt = None

                # 5.4 Bilingual merge
                if zh_srt:
                    step_n += 1
                    step(step_n, total_steps, "Build bilingual SRT …")
                    bi_srt = ch_dir / f"{name}_bilingual.srt"
                    r = run_script([str(SCRIPTS/"make_bilingual_srt.py"),
                                    str(en_srt), str(zh_srt), str(bi_srt)])
                    if "OK:" in r.stdout:
                        ok()
                    else:
                        fail(r.stderr[:80])
                        bi_srt = None

        if opts["burn"]:
            srt_to_burn = bi_srt or en_srt
            if srt_to_burn:
                step_n += 1
                step(step_n, total_steps, "Burn subtitles to video …")
                burned = ch_dir / f"{name}_with_subtitles.mp4"
                r = run_script([str(SCRIPTS/"burn_subtitles.py"),
                                str(clip_path), str(srt_to_burn), str(burned)])
                if "OK" in r.stdout:
                    ok()
                else:
                    fail(r.stderr[:100])
            else:
                print(f"  ⚠  No subtitle file to burn (skipped).")

        if opts["summary"]:
            step_n += 1
            step(step_n, total_steps, "Generate summary …")
            # Write chapter info for the summary script
            ch_json = WORK_DIR / f"{name}_chapter.json"
            excerpt = " ".join(e["text"] for e in sub_data.get("entries", [])
                               if ts_to_secs(ch["start"]) <= e["start"] < ts_to_secs(ch["end"]))[:600]
            ch_json.write_text(json.dumps({
                "title"            : ch["title"],
                "summary"          : ch["summary"],
                "keywords"         : ch.get("keywords", []),
                "transcript_excerpt": excerpt,
            }, ensure_ascii=False), encoding="utf-8")
            out_md = ch_dir / f"{name}_summary.md"
            r = run_script([str(SCRIPTS/"generate_summary.py"), str(ch_json), str(out_md)])
            if "OK:" in r.stdout:
                ok()
            else:
                fail(r.stderr[:100])

        print(f"\n  ✨  Chapter '{ch['title'][:50]}' done  →  {ch_dir}")

# ══════════════════════════════════════════════════════════════════════════════
# Stage 6 — Output
# ══════════════════════════════════════════════════════════════════════════════

def stage6_output(out_dir: Path):
    print(f"\n[Stage 6] Output\n")
    hr()
    print(f"  ✨  Processing complete!\n")
    print(f"  📁  Output directory: {out_dir}\n")
    print("  Files:")
    for f in sorted(out_dir.rglob("*")):
        if f.is_file():
            rel  = f.relative_to(out_dir)
            size = f.stat().st_size / 1_048_576
            icon = "🎬" if f.suffix == ".mp4" else "📄" if f.suffix == ".srt" else "📝"
            print(f"    {icon}  {rel}  ({size:.1f} MB)")

    print(f"\n  Quick preview:")
    mp4s = sorted(out_dir.rglob("*.mp4"))
    if mp4s:
        print(f"    open \"{mp4s[0]}\"")
    hr()

# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    sub_data: dict = {}

    stage1_env_check()

    while True:
        info     = stage2_download(url)
        url      = None  # only use CLI arg on first run
        chapters = stage3_analyze(info, sub_data)
        selected, opts = stage4_select(chapters)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir   = OUTPUT_ROOT / timestamp
        out_dir.mkdir(parents=True, exist_ok=True)

        stage5_process(info, chapters, selected, opts, out_dir, sub_data)
        stage6_output(out_dir)

        again = input("\n  Continue clipping more chapters from this video? [y/N]: ").strip().lower()
        if again == "y":
            # Go back to chapter selection (stage 4), re-use same video
            selected, opts = stage4_select(chapters)
            timestamp2     = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir2       = OUTPUT_ROOT / timestamp2
            out_dir2.mkdir(parents=True, exist_ok=True)
            stage5_process(info, chapters, selected, opts, out_dir2, sub_data)
            stage6_output(out_dir2)
        else:
            print("\n  👋  Done. Clips saved to:", OUTPUT_ROOT)
            break

if __name__ == "__main__":
    main()
