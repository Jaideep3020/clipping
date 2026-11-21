#!/usr/bin/env python3
"""
scripts/generate_summary.py  —  Stage 5.6: Generate social media summary
Usage: python3 scripts/generate_summary.py <chapter_json_file> [output_md]
chapter_json: {"title": "...", "summary": "...", "keywords": [...], "transcript_excerpt": "..."}
"""
import sys, os, json
from pathlib import Path
from datetime import datetime

chapter_path = Path(sys.argv[1])
chapter      = json.loads(chapter_path.read_text(encoding="utf-8"))
out_md       = Path(sys.argv[2]) if len(sys.argv) > 2 \
               else chapter_path.with_suffix(".summary.md")

PROMPT = f"""You are a social media content strategist specializing in short-form video.

Based on the following video clip information, generate engaging social media copy.

**Clip title**: {chapter.get('title', '')}
**Summary**: {chapter.get('summary', '')}
**Keywords**: {', '.join(chapter.get('keywords', []))}
**Transcript excerpt**: {chapter.get('transcript_excerpt', '')[:800]}

Generate a JSON object with this exact schema:
{{
  "xiaohongshu": {{
    "title": "<hook title ≤20 chars, Chinese>",
    "body": "<2-3 key points, conversational Chinese, 100-150 chars>",
    "hashtags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"]
  }},
  "douyin_tiktok": {{
    "hook": "<first sentence to hook viewers in <3s, Chinese>",
    "script": "<voiceover script 50-80 chars>",
    "cta": "<call to action>"
  }},
  "youtube_shorts": {{
    "title": "<SEO title in English ≤60 chars>",
    "description": "<2-sentence English description with keywords>",
    "tags": ["<tag1>", "<tag2>", "<tag3>"]
  }},
  "core_insight": "<the single most shareable idea from this clip, in English>"
}}
Output ONLY the JSON, no markdown fences."""

def call_gemini(prompt: str) -> dict:
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp  = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(resp.text)

def call_openai(prompt: str) -> dict:
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

data = None
for fn in [call_gemini, call_openai]:
    try:
        data = fn(PROMPT)
        break
    except EnvironmentError:
        pass
    except Exception as e:
        print(f"⚠ {e}", file=sys.stderr)

if not data:
    data = {"error": "No LLM API available", "title": chapter.get("title", "")}

# Write Markdown
xhs  = data.get("xiaohongshu", {})
tt   = data.get("douyin_tiktok", {})
yt   = data.get("youtube_shorts", {})
ins  = data.get("core_insight", "")

md = f"""# 📝 Summary — {chapter.get('title', '')}
_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_

---

## 💡 Core Insight
> {ins}

---

## 🌸 小红书 (Xiaohongshu)
**标题**: {xhs.get('title', '')}

{xhs.get('body', '')}

{' '.join('#' + t for t in xhs.get('hashtags', []))}

---

## 🎵 抖音 / TikTok
**开场钩子**: {tt.get('hook', '')}

**文案**: {tt.get('script', '')}

**CTA**: {tt.get('cta', '')}

---

## 📺 YouTube Shorts
**Title**: {yt.get('title', '')}

**Description**: {yt.get('description', '')}

**Tags**: {', '.join(yt.get('tags', []))}
"""

out_md.write_text(md, encoding="utf-8")
print(f"OK: {out_md}")
