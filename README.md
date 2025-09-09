# Public Vinyl Radio – Prompt & YouTube Tools

Utilities for generating LLM-ready prompts and YouTube assets from your show data.

## Requirements
- Python 3.9+
- PyYAML (for parsing MDX/Markdown front matter with nested tracklists)

Optional setup (recommended):

```zsh
# create & activate a virtualenv (macOS/zsh)
python3 -m venv .venv
source .venv/bin/activate

# install dependency for YAML parsing
pip install pyyaml
```

## Scripts

### 1) pvr_prompt_gen.py
Reads an episode JSON file and outputs a strict prompt to generate YAML + Markdown for a show post. It injects the JSON (with some fields stripped) into the prompt template.

Usage:
```zsh
# print prompt to stdout
./pvr_prompt_gen.py path/to/episode.json

# write to a file
./pvr_prompt_gen.py path/to/episode.json -o prompt.txt

# pretty-print JSON inside the prompt
./pvr_prompt_gen.py path/to/episode.json --pretty

# strip additional keys anywhere in the JSON
./pvr_prompt_gen.py path/to/episode.json --drop embedding vectors ai_meta
```

Notes:
- Default drop fields include common embedding/AI metadata: `embedding`, `embeddings`, `vector`, `vectors`, `audio_embedding`, `ml`, `ai_meta`, `openai_meta`, `_meta`, `_internal`.
- If the input JSON is a dict or a list, it is preserved as-is (lists are not truncated).

### 2) pvr_youtube_prompt_gen.py
Generates either:
- a model prompt for creating a YouTube Title + Description (default), or
- a timestamped YouTube comment from the `tracklist` using `duration_seconds` (`--comment`).

Supported inputs:
- MDX/Markdown files with YAML front matter at the top, or
- standalone YAML files containing the front matter keys.

Common fields used from front matter:
- `title`, `slug`, `host`/`hosts`, `tags` (or `styles`/`genres`), `tracklist` (array of `{ title, artist, duration_seconds, ... }`).

Usage:
```zsh
# Generate prompt (default)
python pvr_youtube_prompt_gen.py ~/Projects/pvr-site/src/content/shows/afronova.mdx | pbcopy

# Generate timestamped YouTube comment
python pvr_youtube_prompt_gen.py ~/Projects/pvr-site/src/content/shows/afronova.mdx --comment | pbcopy
```

Timestamped comment format:
- Each line shows the track start time, title (italicized), and artist.
- Timestamps are cumulative sums of `duration_seconds`.
- Formats as `M:SS` or `H:MM:SS` when exceeding 60 minutes.

Example line:
```
0:00 *Get Away* – Umoja I-nity
```

Prompt generation includes:
- Title/Description requirements, SEO cues, links (Show URL, IG, Mixcloud), and a normalized tracklist for the model to infer styles/eras/regions.
- Basic IG handle mapping inside the script (`IG_HANDLES`). Add entries as needed.

## Troubleshooting
- YAML parsing errors or missing nested `tracklist` usually means PyYAML is not installed. Install it with:
```zsh
pip install pyyaml
```
- If no `tracklist` or `duration_seconds` are present, the `--comment` output may be empty or show repeated timestamps.
- On macOS you can pipe to clipboard with `| pbcopy` as shown above.

## Project hygiene
A Python-friendly `.gitignore` is included to ignore `__pycache__/`, virtualenvs, build artifacts, test caches, and editor/OS files.