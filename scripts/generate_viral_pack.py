#!/usr/bin/env python3
"""
scripts/generate_viral_pack.py — Viral Reach & Social Distribution Pack Generator
================================================================================
Generates high-CTR titles, curiosity-gap hooks, hashtag clusters, and engagement
questions tailored for TikTok, YouTube Shorts, and Instagram Reels algorithms.

Usage:
    python scripts/generate_viral_pack.py <clip_title> <transcript_excerpt> [output_file]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

VIRAL_PACK_PROMPT = """You are a viral social media growth hacker and short-form video strategist with over 100M+ views across TikTok, YouTube Shorts, and Instagram Reels.

Based on this video clip title and transcript excerpt:
TITLE: {clip_title}
TRANSCRIPT: {transcript_excerpt}

Generate a viral distribution pack adhering to short-form algorithm best practices:
1. Three High-CTR Title Variants:
   - Curiosity Gap: creates intense itch to know the answer
   - Contrarian / Bold Statement: challenges common assumptions
   - Direct High Value: tells the viewer exactly what skill/insight they will learn
2. TikTok / Shorts Caption:
   - Punchy opening line (1 sentence)
   - 2-3 value bullet points
   - Engagement question / CTA that drives comments (comments heavily boost algorithm ranking)
3. Hashtags: 3 tiers of hashtags:
   - Broad reach (#fyp, #shorts, #viral)
   - Niche specific (3-5 tags)
   - Keyword / Topic specific (3-5 tags)
4. Hook Strategy Note: Why this moment stops the scroll in the first 2 seconds.

Return strictly valid JSON:
{{
  "curiosity_title": "...",
  "contrarian_title": "...",
  "value_title": "...",
  "caption_body": "...",
  "engagement_question": "...",
  "hashtags": ["#shorts", "#viral", "..."],
  "algorithm_growth_tip": "..."
}}
"""

def generate_viral_pack(title: str, transcript: str) -> dict:
    from engine.clipper_engine import _call_llm
    prompt = VIRAL_PACK_PROMPT.format(clip_title=title, transcript_excerpt=transcript[:2500])
    data, _ = _call_llm(prompt)
    return data

def main():
    parser = argparse.ArgumentParser(description="Generate viral packaging for short-form clips")
    parser.add_argument("title", help="Clip title")
    parser.add_argument("transcript", help="Transcript excerpt or path to text/json file")
    parser.add_argument("output", nargs="?", default="", help="Output markdown file path")
    args = parser.parse_args()

    # Load transcript if file
    t_text = args.transcript
    if Path(args.transcript).exists():
        t_text = Path(args.transcript).read_text(encoding="utf-8", errors="replace")[:3000]

    print(f"Generating viral reach pack for: '{args.title}' ...")
    pack = generate_viral_pack(args.title, t_text)

    tags_str = " ".join(pack.get("hashtags", ["#shorts", "#fyp", "#viral"]))

    md = f"""# 🚀 Viral Reach & Distribution Pack
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Original Topic**: {args.title}

---

## 🎯 High-CTR Title Options (Pick One)
1. **Curiosity Gap**: `{pack.get('curiosity_title', '')}`
2. **Contrarian / Shock**: `{pack.get('contrarian_title', '')}`
3. **Direct Value**: `{pack.get('value_title', '')}`

---

## 📱 Optimized Post Caption (Copy & Paste)
{pack.get('caption_body', '')}

👉 **Question**: {pack.get('engagement_question', 'What do you think?')}

{tags_str}

---

## 💡 Algorithm Growth Tip
> {pack.get('algorithm_growth_tip', 'Post during peak viewing hours (12-2 PM or 7-9 PM local time).')}
"""

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(md, encoding="utf-8")
        print(f"Saved viral pack to: {out_p}")
    else:
        print("\n" + md)

if __name__ == "__main__":
    main()
