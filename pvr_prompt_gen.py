#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Public Vinyl Radio — Prompt Generator
Reads an episode JSON and outputs a prompt template with the JSON injected
so you can feed it to your LLM to produce YAML + markdown.

Usage:
  ./pvr_prompt_gen.py episode.json > prompt.txt
  ./pvr_prompt_gen.py episode.json -o prompt.txt
  ./pvr_prompt_gen.py episode.json -o prompt.txt --drop embedding vectors ai_meta
  ./pvr_prompt_gen.py episode.json --pretty
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Set

DEFAULT_DROP_FIELDS = {
    "embedding", "embeddings", "vector", "vectors",
    "audio_embedding", "ml", "ai_meta", "openai_meta",
    "_meta", "_internal",
}

PROMPT_TEMPLATE = """You are generating a new blog post in my standard YAML + markdown format for Public Vinyl Radio.

### INPUT DATA
Episode JSON:
{EPISODE_JSON}

### OUTPUT FORMAT
1) Start with YAML front matter (between `---`), including:
   - title
   - description
   - episode
   - date
   - tags
   - slug
   - coverImage
   - host
   - youtubeId
   - template
   - tracklist (array of objects with title and artist, same order as input)

2) After the YAML, write:
   - H1 with the episode title
   - 1–2 paragraphs expanding the description (vibe, styles, atmosphere, notable transitions)
   - <ResponsiveYouTube videoId={"<YOUTUBE ID>"} />
   - "Tracklist Deep Dive" section
   - For each track, in order:
     - **<Artist> – <Title>**
       1–2 sentence commentary (texture, groove, instrumentation, energy/mood shift)
   - End with a short wrap‑up line.

3) Style:
   - Warm, descriptive, music‑focused; concise but vivid.
   - Avoid inventing artists/tracks. Use exactly what’s in the input.
   - Keep commentary specific (mention textures/grooves/mood shifts/instrumental details).

4) Do NOT include any extra boilerplate besides the YAML front matter and the markdown body.

Return ONLY the YAML front matter and markdown body (no explanations).
"""

def strip_fields(obj: Any, drop: Set[str]) -> Any:
    """Recursively remove keys (case-insensitive) anywhere in the structure."""
    if isinstance(obj, dict):
        lowered = {k.lower() for k in drop}
        return {k: strip_fields(v, drop) for k, v in obj.items() if k.lower() not in lowered}
    if isinstance(obj, list):
        return [strip_fields(x, drop) for x in obj]
    return obj

def main():
    ap = argparse.ArgumentParser(description="Generate an LLM prompt by injecting episode JSON.")
    ap.add_argument("input", type=Path, help="Episode JSON file")
    ap.add_argument("-o", "--output", type=Path, help="Write prompt to this file (otherwise prints to stdout)")
    ap.add_argument("--drop", nargs="*", default=[], help="Additional keys to strip anywhere in the JSON")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON in the prompt (default is compact)")
    args = ap.parse_args()

    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # If input is a list or dict, keep as is (do not reduce to first object)

    drop_keys = DEFAULT_DROP_FIELDS.union(set(args.drop))
    cleaned = strip_fields(raw, drop_keys)

    json_text = json.dumps(cleaned, ensure_ascii=False, indent=(2 if args.pretty else None))
    prompt = PROMPT_TEMPLATE.replace("{EPISODE_JSON}", json_text)

    if args.output:
        args.output.write_text(prompt, encoding="utf-8")
        print(f"✅ Wrote prompt to {args.output}")
    else:
        print(prompt)

if __name__ == "__main__":
    main()