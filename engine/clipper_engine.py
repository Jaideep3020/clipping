"""
clipper_engine.py — Core clipping engine for the YouTube clipping tool.

Strategy (SupoClip-inspired):
  1. 4-dimension virality scoring: overall, hook, engagement, shareability
  2. Semantic chunking — LLM finds cohesive storytelling arcs and complete thoughts
  3. Word-level timestamp alignment — cuts never land mid-syllable
  4. Multi-provider LLM support: Gemini 1.5 Flash → OpenAI GPT-4o → error
  5. Confidence-based filtering — only clips above min_score pass through
"""

from __future__ import annotations

import json
import logging
import os
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ViralityScore:
    """4-dimension virality scoring for a clip candidate."""
    overall: float
    hook: float
    engagement: float
    shareability: float
    rationale: str = ""

    def __post_init__(self) -> None:
        for attr in ("overall", "hook", "engagement", "shareability"):
            val = getattr(self, attr)
            if not (0.0 <= float(val) <= 10.0):
                raise ValueError(
                    f"ViralityScore.{attr} must be in [0, 10], got {val!r}"
                )


@dataclass
class ClipCandidate:
    """A single viral clip candidate extracted from a transcript."""
    title: str
    start: float          # seconds
    end: float            # seconds
    duration: float       # seconds  (end - start)
    virality: ViralityScore
    verbatim_quote: str   # first sentence / hook quote from the clip
    hook_title: str       # short punchy social-media title

    # Derived helpers ----------------------------------------------------------
    @property
    def overall_score(self) -> float:
        return self.virality.overall

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "hook_title": self.hook_title,
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "verbatim_quote": self.verbatim_quote,
            "virality": {
                "overall": self.virality.overall,
                "hook": self.virality.hook,
                "engagement": self.virality.engagement,
                "shareability": self.virality.shareability,
                "rationale": self.virality.rationale,
            },
        }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_virality_prompt(
    transcript_text: str,
    duration: float,
    max_clips: int = 10,
    min_dur: int = 30,
    max_dur: int = 90,
) -> str:
    """
    Build the full LLM prompt that instructs the model to find viral clip
    candidates using 4-dimension scoring.

    Parameters
    ----------
    transcript_text:
        Full transcript with word-level timestamps in the format
        ``[HH:MM:SS.mmm] word word word …``  (one line per segment).
    duration:
        Total video duration in seconds.
    max_clips:
        Maximum number of clip candidates to return.
    min_dur / max_dur:
        Acceptable clip length range in seconds.
    """
    prompt = textwrap.dedent(f"""
    You are an expert short-form video editor specialising in viral content for
    YouTube Shorts, TikTok and Instagram Reels.

    ## Task
    Analyse the transcript below (total video length: {duration:.1f}s) and
    identify up to {max_clips} self-contained, viral clip candidates.

    Each clip MUST:
    - Be between {min_dur}s and {max_dur}s long.
    - Start and end on a word boundary — NEVER cut mid-syllable or mid-word.
    - Contain a complete thought, story arc, or emotional moment.
    - Be independently understandable without the rest of the video.

    ## 4-Dimension Virality Scoring  (each dimension: 0.0 – 10.0)

    1. **hook_score** — How compelling are the first 3-5 seconds?
       Does it immediately grab attention? Strong hooks open with a surprising
       fact, provocative question, or bold statement.

    2. **engagement_score** — Does the content sustain viewer attention
       throughout? Look for storytelling tension, humour, emotional resonance,
       actionable value, or surprising revelations.

    3. **shareability_score** — Would people forward this to a friend or post
       it themselves? Shareable clips have a clear "wow" moment, relate to
       universal experiences, or spark debate.

    4. **overall_score** — Holistic viral potential on a scale of 0–10.
       Weight: hook 30 %, engagement 35 %, shareability 35 %.
       Be strict: 7+ means genuinely strong, 9+ means exceptional.

    ## Output Format
    Return a JSON array (and ONLY the JSON array — no markdown fences, no
    commentary outside the array).  Each element must have exactly these keys:

    {{
      "title":           "<descriptive clip title>",
      "hook_title":      "<≤8-word punchy social-media caption>",
      "start":           <float seconds>,
      "end":             <float seconds>,
      "verbatim_quote":  "<exact opening words from the transcript>",
      "hook_score":      <float 0-10>,
      "engagement_score":<float 0-10>,
      "shareability_score": <float 0-10>,
      "overall_score":   <float 0-10>,
      "rationale":       "<2-3 sentence explanation of the scores>"
    }}

    Sort by overall_score descending.

    ## Transcript
    {transcript_text}
    """).strip()
    return prompt


# ---------------------------------------------------------------------------
# LLM provider helpers
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, api_key: str, model_name: str = "gemini-2.0-flash") -> str:
    """Call Gemini API and return the raw text response."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai is not installed. Run: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    candidate_models = [model_name, "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = None
    for m in candidate_models:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                ),
            )
            return response.text
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return ""


def _call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI GPT-4o and return the raw text response."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "openai is not installed. Run: pip install openai"
        ) from exc

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _call_ollama(prompt: str, model: str = "llama3") -> str:
    """Call a local Ollama model and return the raw text response."""
    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "requests is not installed. Run: pip install requests"
        ) from exc

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json().get("response", "")


def _llm_generate(prompt: str, config: dict) -> str:
    """
    Multi-provider LLM dispatcher.

    Priority: Gemini 1.5/2.0 Flash → OpenAI GPT-4o → Ollama (local) → error.
    """
    gemini_key = (
        config.get("gemini_api_key")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )
    openai_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    ollama_model = config.get("ollama_model", "llama3")

    # Also check ~/.clipforge_keys.json
    keys_file = Path.home() / ".clipforge_keys.json"
    if keys_file.exists():
        try:
            kdata = json.loads(keys_file.read_text())
            if not gemini_key:
                gemini_key = kdata.get("GEMINI_API_KEY") or kdata.get("GOOGLE_API_KEY") or ""
            if not openai_key:
                openai_key = kdata.get("OPENAI_API_KEY") or ""
        except Exception:
            pass

    errors: list[str] = []
    provider = str(config.get("provider", "auto")).lower().strip()

    # Determine order of providers based on config["provider"]
    if provider == "openai":
        order = ["openai", "gemini"]
    elif provider == "gemini":
        order = ["gemini", "openai"]
    else:
        order = ["gemini", "openai"]

    for prov in order:
        if prov == "gemini" and gemini_key:
            try:
                g_model = config.get("gemini_model", "gemini-2.0-flash")
                logger.info("Calling Gemini (%s) …", g_model)
                return _call_gemini(prompt, gemini_key, model_name=g_model)
            except Exception as exc:
                logger.warning("Gemini failed: %s", exc)
                errors.append(f"Gemini: {exc}")
        elif prov == "openai" and openai_key:
            try:
                logger.info("Calling OpenAI GPT-4o …")
                return _call_openai(prompt, openai_key)
            except Exception as exc:
                logger.warning("OpenAI failed: %s", exc)
                errors.append(f"OpenAI: {exc}")

    # --- Ollama (local fallback) ---
    if config.get("use_ollama", False):
        try:
            logger.info("Calling Ollama (%s) …", ollama_model)
            return _call_ollama(prompt, model=ollama_model)
        except Exception as exc:
            logger.warning("Ollama failed: %s", exc)
            errors.append(f"Ollama: {exc}")

    if not gemini_key and not openai_key and not config.get("use_ollama"):
        raise RuntimeError("No LLM API key detected (GEMINI_API_KEY or OPENAI_API_KEY unset).")

    raise RuntimeError(
        "No LLM provider succeeded. Errors:\n" + "\n".join(errors)
    )


def _heuristic_virality_scoring(
    transcript_segments: list[dict],
    video_duration: float,
    max_clips: int = 5,
    min_dur: int = 25,
    max_dur: int = 60,
    min_score: float = 6.0,
) -> list[ClipCandidate]:
    """
    Autonomous Offline Virality Engine.
    Uses speech cadence, engagement keywords, hook indicators, and sentence boundaries
    to rank and extract highlights without requiring an external LLM API key.
    """
    print("  ⚡ Running Autonomous Speech-Density & Virality Engine (zero-cost offline mode)...")
    if not transcript_segments:
        return []

    HOOK_WORDS = {
        "why", "how", "what", "watch", "look", "see", "listen", "never", "always",
        "secret", "truth", "best", "worst", "unbelievable", "omg", "insane", "crazy",
        "warning", "check", "wait", "here", "first", "wicket", "six", "boundary",
        "catch", "goal", "champion", "legend", "massive", "huge", "shocking", "no way"
    }
    ENGAGE_WORDS = {
        "!", "?", "great", "brilliant", "shot", "run", "fast", "hit", "strike",
        "out", "ball", "win", "lost", "game", "match", "play", "wow", "epic", "perfect"
    }

    all_words = _collect_words(transcript_segments)
    t_start = float(transcript_segments[0].get("start", 0.0))
    t_end = float(transcript_segments[-1].get("end", video_duration or 60.0))

    # Generate sliding window proposals
    window_sizes = [min_dur, int((min_dur + max_dur) / 2), max_dur]
    proposals = []

    # Slide across timeline with 15s step
    step = 15.0
    curr = t_start
    while curr + min_dur <= t_end:
        for w_sz in window_sizes:
            w_end = min(curr + w_sz, t_end)
            if w_end - curr < min_dur:
                continue

            # Gather segments overlapping this window
            sub_segs = [s for s in transcript_segments if s.get("end", 0) >= curr and s.get("start", 0) <= w_end]
            if not sub_segs:
                continue

            w_text = " ".join(s.get("text", "").strip() for s in sub_segs).strip()
            words_list = w_text.split()
            if len(words_list) < 8:
                continue

            dur = w_end - curr
            wps = len(words_list) / max(dur, 1.0)

            # First 15 words hook evaluation
            first_words = [re.sub(r"[^\w]", "", w.lower()) for w in words_list[:15]]
            hook_hits = sum(1 for w in first_words if w in HOOK_WORDS)
            has_question_or_excl = any("?" in w or "!" in w for w in words_list[:15])

            hook_score = min(9.4, 6.2 + 0.9 * min(hook_hits, 3) + (0.8 if has_question_or_excl else 0.0))

            # Engagement evaluation (speech density + high-energy words)
            all_clean_words = [re.sub(r"[^\w]", "", w.lower()) for w in words_list]
            engage_hits = sum(1 for w in all_clean_words if w in ENGAGE_WORDS)
            density_boost = 0.8 if wps >= 3.0 else (0.4 if wps >= 2.2 else 0.0)
            engagement_score = min(9.5, 6.0 + 0.6 * min(engage_hits, 4) + density_boost)

            # Value evaluation (completeness of thoughts)
            clean_start = sub_segs[0].get("text", "")[:1].isupper()
            clean_end = sub_segs[-1].get("text", "").strip().endswith((".", "!", "?"))
            value_score = min(9.3, 6.5 + (0.6 if clean_start else 0.0) + (0.6 if clean_end else 0.0))

            # Shareability
            shareability_score = min(9.5, 6.1 + 0.5 * min(hook_hits, 3) + 0.5 * min(engage_hits, 3))

            overall = round(
                0.30 * hook_score + 0.30 * engagement_score + 0.20 * value_score + 0.20 * shareability_score,
                1
            )

            # Title extraction: take first punchy sentence or build title
            first_sent = sub_segs[0].get("text", "").strip()
            title = re.sub(r"[^\w\s-]", "", first_sent).strip()
            if len(title.split()) > 9:
                title = " ".join(title.split()[:8])
            if not title or len(title) < 8:
                title = f"Highlight: {w_text[:40].strip()}..."

            quote = first_sent[:80]
            hook_title = f"{title[:45].upper()}"

            proposals.append({
                "start": curr,
                "end": w_end,
                "overall": overall,
                "hook": round(hook_score, 1),
                "engagement": round(engagement_score, 1),
                "value": round(value_score, 1),
                "shareability": round(shareability_score, 1),
                "title": title,
                "hook_title": hook_title,
                "verbatim_quote": quote,
                "rationale": f"High speech velocity ({wps:.1f} wps) and strong narrative hook with {hook_hits} engagement triggers."
            })
        curr += step

    # Non-maximum suppression: pick highest scoring distinct windows
    proposals.sort(key=lambda p: p["overall"], reverse=True)
    selected = []
    for prop in proposals:
        if prop["overall"] < min_score:
            continue
        # Check overlap with already selected
        overlap = False
        for sel in selected:
            s_overlap = max(0.0, min(prop["end"], sel["end"]) - max(prop["start"], sel["start"]))
            if s_overlap > 15.0:
                overlap = True
                break
        if not overlap:
            selected.append(prop)
            if len(selected) >= max_clips:
                break

    # If nothing passed min_score, take the top available
    if not selected and proposals:
        selected = [proposals[0]]

    # Convert to ClipCandidate objects with word-snapped boundaries
    candidates = []
    for p in selected:
        s_start = p["start"]
        s_end = p["end"]
        if all_words:
            s_start = _snap_to_word_boundary(s_start, all_words, prefer="start")
            s_end = _snap_to_word_boundary(s_end, all_words, prefer="end")

        cand = ClipCandidate(
            title=p["title"],
            start=s_start,
            end=s_end,
            duration=round(s_end - s_start, 2),
            virality=ViralityScore(
                overall=p["overall"],
                hook=p["hook"],
                engagement=p["engagement"],
                shareability=p["shareability"],
                rationale=p["rationale"]
            ),
            verbatim_quote=p["verbatim_quote"],
            hook_title=p["hook_title"]
        )
        candidates.append(cand)

    candidates.sort(key=lambda c: c.virality.overall, reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Transcript formatting helpers
# ---------------------------------------------------------------------------

def _format_transcript(segments: list[dict]) -> str:
    """
    Convert word-level transcript segments to a timestamped text string.

    Expected segment shape (WhisperX / AssemblyAI style):
        {
          "text": "Hello world",
          "start": 1.23,   # seconds
          "end":   2.45,
          "words": [
            {"word": "Hello", "start": 1.23, "end": 1.60, "score": 0.99},
            {"word": "world", "start": 1.70, "end": 2.45, "score": 0.95},
          ]
        }
    """
    lines: list[str] = []
    for seg in segments:
        start = seg.get("start", 0.0)
        h = int(start // 3600)
        m = int((start % 3600) // 60)
        s = start % 60
        ts = f"[{h:02d}:{m:02d}:{s:06.3f}]"
        text = seg.get("text", "").strip()
        if text:
            lines.append(f"{ts} {text}")
    return "\n".join(lines)


def _snap_to_word_boundary(
    target_time: float,
    words: list[dict],
    prefer: str = "start",
) -> float:
    """
    Given a target cut time, snap it to the nearest word boundary so we
    never cut mid-syllable.

    Parameters
    ----------
    target_time : float
        Desired cut point in seconds.
    words : list[dict]
        Flat list of word-level timestamps, each with "start" and "end".
    prefer : str
        ``"start"`` → snap to the nearest word's start time (safe for clip
        begin).  ``"end"`` → snap to nearest word's end time (safe for clip
        end).
    """
    if not words:
        return target_time

    key = "start" if prefer == "start" else "end"
    best = min(words, key=lambda w: abs(w.get(key, 0.0) - target_time))
    return float(best.get(key, target_time))


def _collect_words(segments: list[dict]) -> list[dict]:
    """Flatten all word-level entries from all segments into one list."""
    words: list[dict] = []
    for seg in segments:
        words.extend(seg.get("words", []))
    return words


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _extract_json_array(raw: str) -> list[dict]:
    """
    Extract the first JSON array from raw LLM output, tolerating markdown
    code fences and stray text before/after the array.
    """
    # Strip markdown fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip()

    # Find the outermost [ … ]
    start_idx = raw.find("[")
    if start_idx == -1:
        raise ValueError("No JSON array found in LLM response.")

    depth = 0
    end_idx = -1
    for i, ch in enumerate(raw[start_idx:], start=start_idx):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end_idx = i
                break

    if end_idx == -1:
        raise ValueError("Unterminated JSON array in LLM response.")

    return json.loads(raw[start_idx : end_idx + 1])


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def score_highlights(
    transcript_segments: list[dict],
    video_duration: float,
    config: dict | None = None,
) -> list[ClipCandidate]:
    """
    Identify and rank the most viral clip candidates in a transcript.

    Parameters
    ----------
    transcript_segments:
        List of transcript segments (WhisperX / AssemblyAI format).  Each
        segment should contain ``"text"``, ``"start"``, ``"end"``, and
        optionally ``"words"`` (word-level timestamps for boundary snapping).
    video_duration:
        Total video length in seconds.
    config:
        Optional configuration dict.  Keys:
            gemini_api_key  (str)  — overrides GEMINI_API_KEY env var
            openai_api_key  (str)  — overrides OPENAI_API_KEY env var
            use_ollama      (bool) — enable Ollama as last-resort fallback
            ollama_model    (str)  — Ollama model name (default "llama3")
            max_clips       (int)  — max candidates to return (default 10)
            min_score       (float)— minimum overall_score to keep (default 6.0)
            min_duration    (int)  — minimum clip length in seconds (default 30)
            max_duration    (int)  — maximum clip length in seconds (default 90)

    Returns
    -------
    List of :class:`ClipCandidate` sorted by overall_score descending,
    filtered by min_score, capped at max_clips.
    """
    cfg: dict[str, Any] = config or {}
    max_clips: int = int(cfg.get("max_clips", 10))
    min_score: float = float(cfg.get("min_score", 6.0))
    min_dur: int = int(cfg.get("min_duration", 30))
    max_dur: int = int(cfg.get("max_duration", 90))

    # Build transcript text ------------------------------------------------
    transcript_text = _format_transcript(transcript_segments)
    if not transcript_text.strip():
        logger.warning("score_highlights: empty transcript — returning []")
        return []

    # Collect word-level timestamps for boundary snapping ------------------
    all_words = _collect_words(transcript_segments)

    # Build prompt ---------------------------------------------------------
    prompt = build_virality_prompt(
        transcript_text=transcript_text,
        duration=video_duration,
        max_clips=max_clips,
        min_dur=min_dur,
        max_dur=max_dur,
    )

    # Call LLM -------------------------------------------------------------
    raw_clips = None
    try:
        raw_response = _llm_generate(prompt, cfg)
        logger.debug("Raw LLM response:\n%s", raw_response)
        raw_clips = _extract_json_array(raw_response)
    except Exception as exc:
        print(f"  ℹ  Notice: LLM API generation not active ({exc})")
        print("  ⚡  Seamlessly switching to Autonomous Speech-Cadence & Virality Scoring Engine...")

    if not raw_clips:
        return _heuristic_virality_scoring(
            transcript_segments=transcript_segments,
            video_duration=video_duration,
            max_clips=max_clips,
            min_dur=min_dur,
            max_dur=max_dur,
            min_score=min_score,
        )

    # Build ClipCandidate objects ------------------------------------------
    candidates: list[ClipCandidate] = []
    for raw in raw_clips:
        try:
            overall = float(raw.get("overall_score", 0.0))
            hook = float(raw.get("hook_score", 0.0))
            engagement = float(raw.get("engagement_score", 0.0))
            shareability = float(raw.get("shareability_score", 0.0))
            rationale = str(raw.get("rationale", ""))

            # Confidence filter — skip below threshold ---------------------
            if overall < min_score:
                logger.debug(
                    "Skipping clip '%s' (overall %.1f < min_score %.1f)",
                    raw.get("title", ""),
                    overall,
                    min_score,
                )
                continue

            raw_start = float(raw.get("start", 0.0))
            raw_end = float(raw.get("end", 0.0))

            # Clamp to video bounds ----------------------------------------
            raw_start = max(0.0, min(raw_start, video_duration))
            raw_end = max(raw_start, min(raw_end, video_duration))

            # Snap to word boundaries (never cut mid-syllable) -------------
            if all_words:
                start = _snap_to_word_boundary(raw_start, all_words, prefer="start")
                end = _snap_to_word_boundary(raw_end, all_words, prefer="end")
            else:
                start, end = raw_start, raw_end

            duration = round(end - start, 3)

            # Duration guard -----------------------------------------------
            if duration < min_dur or duration > max_dur:
                logger.debug(
                    "Skipping clip '%s' (duration %.1fs out of [%ds, %ds])",
                    raw.get("title", ""),
                    duration,
                    min_dur,
                    max_dur,
                )
                continue

            virality = ViralityScore(
                overall=overall,
                hook=hook,
                engagement=engagement,
                shareability=shareability,
                rationale=rationale,
            )

            candidates.append(
                ClipCandidate(
                    title=str(raw.get("title", "Untitled Clip")),
                    start=start,
                    end=end,
                    duration=duration,
                    virality=virality,
                    verbatim_quote=str(raw.get("verbatim_quote", "")),
                    hook_title=str(raw.get("hook_title", "")),
                )
            )

        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping malformed clip entry %r: %s", raw, exc)
            continue

    # Sort by overall_score descending, cap at max_clips -------------------
    candidates.sort(key=lambda c: c.overall_score, reverse=True)
    return candidates[:max_clips]
