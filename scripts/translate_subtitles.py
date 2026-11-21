#!/usr/bin/env python3
"""
scripts/translate_subtitles.py  —  Stage 5.3: Batch-translate SRT to Chinese
Skill rule: 20 entries per batch (saves ~95% API calls, keeps consistency)
Usage: python3 scripts/translate_subtitles.py <input_srt> [output_srt]
Uses Gemini first, then OpenAI as fallback (same pattern as pipeline.py).
"""
import sys, os, json, re
from pathlib import Path

SRT_ENTRY = re.compile(
    r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)",
    re.DOTALL
)

def parse_srt(text: str) -> list[dict]:
    return [
        {"idx": m.group(1), "start": m.group(2), "end": m.group(3), "text": m.group(4).strip()}
        for m in SRT_ENTRY.finditer(text.strip() + "\n\n")
    ]

def build_srt(entries: list[dict]) -> str:
    blocks = []
    for e in entries:
        blocks.append(f"{e['idx']}\n{e['start']} --> {e['end']}\n{e['text']}\n")
    return "\n".join(blocks)

SYSTEM = (
    "You are a professional subtitle translator. "
    "Translate each numbered English subtitle line to Simplified Chinese. "
    "Rules: preserve technical terms accurately; use natural spoken Chinese; "
    "keep it concise. "
    "Return ONLY valid JSON: an array of objects {\"idx\": \"<num>\", \"zh\": \"<translation>\"}. "
    "No extra text, no markdown."
)

BATCH_SIZE = 20

def translate_batch_gemini(batch: list[dict]) -> list[dict]:
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    model  = genai.GenerativeModel("gemini-1.5-flash")
    prompt = SYSTEM + "\n\nSubtitles:\n" + json.dumps(
        [{"idx": e["idx"], "en": e["text"]} for e in batch], ensure_ascii=False
    )
    resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(resp.text)

def translate_batch_openai(batch: list[dict]) -> list[dict]:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    prompt = json.dumps([{"idx": e["idx"], "en": e["text"]} for e in batch], ensure_ascii=False)
    resp   = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    # GPT might wrap in an object
    return data if isinstance(data, list) else data.get("translations", data.get("subtitles", []))

def translate_batch(batch: list[dict]) -> dict:
    for fn in [translate_batch_gemini, translate_batch_openai]:
        try:
            results = fn(batch)
            return {str(r["idx"]): r["zh"] for r in results}
        except EnvironmentError as e:
            print(f"  ⚠  {e}", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠  Translation error: {e}", file=sys.stderr)
    raise RuntimeError("No translation API available.")

# ─── Main ─────────────────────────────────────────────────────────────────────
in_srt  = Path(sys.argv[1])
out_srt = Path(sys.argv[2]) if len(sys.argv) > 2 else in_srt.with_name(in_srt.stem + "_zh.srt")

entries = parse_srt(in_srt.read_text(encoding="utf-8"))
total   = len(entries)
zh_map  = {}

for i in range(0, total, BATCH_SIZE):
    batch = entries[i : i + BATCH_SIZE]
    pct   = int((i / total) * 100)
    done  = int(pct / 10) * "█"
    empty = (10 - len(done)) * "░"
    print(f"  Translating [{done}{empty}] {pct}% ({i}/{total})", end="\r")
    try:
        result = translate_batch(batch)
        zh_map.update(result)
    except RuntimeError as e:
        print(f"\n  ✗ {e}")
        sys.exit(1)

print(f"  Translated  [██████████] 100% ({total}/{total})     ")

# Build translated SRT
for e in entries:
    e["text"] = zh_map.get(str(e["idx"]), e["text"])

out_srt.write_text(build_srt(entries), encoding="utf-8")
print(f"OK: {out_srt}")
