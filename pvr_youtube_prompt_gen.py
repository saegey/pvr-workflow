#!/usr/bin/env python3
"""
YouTube prompt + timestamped comment generator

Usage:
    python pvr_youtube_prompt_gen.py path/to/post.mdx
    python pvr_youtube_prompt_gen.py path/to/frontmatter.yml
    python pvr_youtube_prompt_gen.py path/to/post.mdx --comment    # print YouTube comment with timestamps

Default prints a GPT prompt for generating Title + Description. Use --comment to print a
timestamped tracklist comment computed from tracklist.duration_seconds.
"""

import os, re, sys, argparse
from pathlib import Path

# --------- CONFIG (edit as needed) ---------
CHANNEL_NAME = "Public Vinyl Radio"
SITE_BASE    = "https://publicvinylradio.com"
SHOWS_PATH   = "/shows"  # final URL => {SITE_BASE}{SHOWS_PATH}/{slug}/
MIXCLOUD_URL = "https://mixcloud.com/public-vinyl-radio"
CHANNEL_IG   = "https://instagram.com/publicvinylradio"

# Map DJ display names -> Instagram handles (no leading @)
IG_HANDLES = {
    "Saegey": "saegey",
    "TOPYEN": "starlustre",
    # add more as needed
}

DEFAULT_STYLES = ["Latin jazz", "salsa", "mambo", "bolero", "cumbia"]

# --------- FRONT MATTER LOADING ---------
def load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    # YAML front matter at top of Markdown/MDX. Handle both closed and unclosed fences.
    if text.startswith("---"):
        # Find the closing fence after the first line; if missing, treat rest of file as YAML
        # Split once to skip the opening fence line
        parts = text.split("\n", 1)
        after_first_line = parts[1] if len(parts) > 1 else ""
        m_close = re.search(r"\n---\s*(?:\n|$)", after_first_line)
        if m_close:
            end_idx = m_close.start()
            raw_yaml = after_first_line[:end_idx]
        else:
            raw_yaml = after_first_line
        return parse_yaml(raw_yaml)

    # Pure YAML file
    if path.suffix.lower() in {".yml", ".yaml"}:
        return parse_yaml(text)

    return {}

def parse_yaml(s: str) -> dict:
    """Parse YAML front matter. Requires PyYAML for nested structures like tracklist."""
    try:
        import yaml  # type: ignore
    except Exception as e:
        # If the file contains nested data (e.g., tracklist) we must have PyYAML
        if re.search(r"^tracklist:\s*$", s, re.M):
            print("This file includes a 'tracklist' with nested YAML. Please install PyYAML: pip install pyyaml", file=sys.stderr)
            raise
        # Fallback for very simple YAML (flat scalars/lists)
        data, current = {}, None
        for line in s.splitlines():
            if not line.strip():
                continue
            if re.match(r"^\s*-\s+", line) and current:
                data.setdefault(current, [])
                data[current].append(line.split("-", 1)[1].strip().strip("'\""))
            elif ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                current = k
                if v == "":
                    data[k] = []
                else:
                    data[k] = v
        return data

    # Use PyYAML for proper parsing
    return yaml.safe_load(s) or {}

# --------- HELPERS ---------
def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-") or "episode"

def pick_list(front: dict, keys=("tags", "styles", "genres")) -> list:
    for k in keys:
        v = front.get(k)
        if isinstance(v, list) and v:
            return v
        if isinstance(v, str) and v.strip():
            return [x.strip() for x in v.split(",")]
    return DEFAULT_STYLES

def format_tracklist(tracklist) -> str:
    if not isinstance(tracklist, list):
        return "(none)"
    lines = []
    for item in tracklist:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        artist = str(item.get("artist", "")).strip()
        year = str(item.get("year", "")).strip()
        album = str(item.get("album", "")).strip()
        parts = []
        if artist and title:
            parts.append(f"{artist} – {title}")
        elif title:
            parts.append(title)
        if year:
            parts.append(f"({year})")
        if album:
            parts.append(f"— {album}")
        line = " ".join(parts).strip()
        if not line:
            continue
        lines.append(f"- {line}")
    return "\n".join(lines) if lines else "(none)"

def extract_year_span(tracklist) -> str:
    years = []
    for item in tracklist or []:
        if not isinstance(item, dict):
            continue
        y = item.get("year")
        if isinstance(y, int):
            years.append(y)
        elif isinstance(y, str) and y.strip().isdigit():
            years.append(int(y.strip()))
    if not years:
        return "(unknown)"
    return f"{min(years)}–{max(years)}" if len(set(years)) > 1 else str(years[0])

def extract_notable_artists(tracklist, limit: int = 8) -> list:
    seen = []
    for item in tracklist or []:
        if not isinstance(item, dict):
            continue
        artist = str(item.get("artist", "")).strip()
        if not artist:
            continue
        # split common separators but keep meaningful combos like "With"
        parts = re.split(r"\s*/\s*|\s*,\s*", artist)
        for p in parts:
            name = p.strip()
            if name and name not in seen:
                seen.append(name)
            if len(seen) >= limit:
                break
        if len(seen) >= limit:
            break
    return seen

def build_show_url(front: dict) -> str:
    slug = front.get("slug") or slugify(str(front.get("title", "")))
    return f"{SITE_BASE.rstrip('/')}{SHOWS_PATH}/{slug}/"

def ig_lines(hosts: list) -> list:
    lines = []
    if hosts:
        for dj in hosts:
            handle = IG_HANDLES.get(dj) or dj.replace(" ", "").lower()
            lines.append(f"{dj}: https://instagram.com/{handle}")
    return lines

# --------- TIMESTAMPED COMMENT ---------
def seconds_to_timestamp(total_seconds: int) -> str:
    total_seconds = max(int(total_seconds or 0), 0)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def build_youtube_comment(tracklist) -> str:
    """Build a YouTube-ready timestamped comment.
    Format per line: 0:00 *Title* – Artist
    Uses cumulative sums of duration_seconds.
    """
    if not isinstance(tracklist, list):
        return ""
    t = 0
    lines = []
    for item in tracklist:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        artist = str(item.get("artist", "")).strip()
        # Emit current start time before adding this track's duration
        ts = seconds_to_timestamp(t)
        display = []
        if title:
            display.append(f"*{title}*")
        if artist:
            if display:
                display.append("–")
            display.append(artist)
        if not display:
            # Skip lines without essential info
            continue
        lines.append(f"{ts} {' '.join(display)}")

        # Advance time
        dur = item.get("duration_seconds")
        # Accept int, numeric string, or float seconds
        if isinstance(dur, (int, float)):
            t += int(dur)
        elif isinstance(dur, str):
            m = re.match(r"^\s*(\d+)(?:\.(\d+))?\s*$", dur)
            if m:
                t += int(float(dur))
        # else: missing/invalid -> treat as 0 (keep same start for next)
    return "\n".join(lines)

# --------- PROMPT FACTORY ---------
def make_prompt(front: dict) -> str:
    title     = str(front.get("title", "")).strip() or "Untitled Set"
    show_url  = build_show_url(front)
    styles    = pick_list(front)
    hosts_raw = front.get("host") or front.get("hosts") or []
    if isinstance(hosts_raw, str):
        hosts = [h.strip() for h in hosts_raw.split(",") if h.strip()]
    else:
        hosts = hosts_raw or []

    tracklist = front.get("tracklist") or []
    tracklist_block = format_tracklist(tracklist)
    year_span = extract_year_span(tracklist)
    notable_artists = ", ".join(extract_notable_artists(tracklist)) or "(none)"

    # Build IG section text for the model to use
    ig_info = "\n".join(ig_lines(hosts))
    if not ig_info:
        ig_info = f"Channel IG: {CHANNEL_IG}"

    # Compose a strict, model-ready instruction
    return f"""You are an expert YouTube copywriter for a vinyl DJ channel called "{CHANNEL_NAME}".
Write a compelling YouTube TITLE and DESCRIPTION for a DJ vinyl-mix video, using the data below.

# Content Data
- Post Title: {title}
- Show URL: {show_url}
- Channel: {CHANNEL_NAME}
- Channel IG: {CHANNEL_IG}
- Mixcloud: {MIXCLOUD_URL}
- Hosts (DJ names): {", ".join(hosts) if hosts else "(none listed)"}
- Host Instagram mapping (use if present; otherwise omit a host line):
{ig_info}
- Styles/Tags (prioritize for SEO + vibe): {", ".join(styles)}
- Tracklist (use to infer era/regions/subgenres; do not invent):
{tracklist_block}
- Year span from tracklist: {year_span}
- Notable artists: {notable_artists}

# Title Requirements
- 70–100 characters when possible.
- Include “All-Vinyl” (or “100% Vinyl”) and 1–2 key styles (e.g., “Latin Jazz, Salsa”).
- Append “| {CHANNEL_NAME}”.
- No clickbait or ALL CAPS; polished and musical.
 - When natural, include a region or era cue inferred from the tracklist (e.g., “West Africa”, “70s Highlife”).

# Description Requirements
- Open with a refined, mood-forward paragraph (sophisticated but rhythmic); mention that it’s all-vinyl.
- Include these link blocks (exact labels):
  🔗 Learn more about this episode, full tracklist, and {CHANNEL_NAME}:
  {show_url}

  📸 Follow us on Instagram:
  {CHANNEL_IG}
{("  " + "\\n  ".join("🎛️ Follow " + dj + " on Instagram:\n  https://instagram.com/" + (IG_HANDLES.get(dj) or dj.replace(" ", "").lower()) for dj in hosts)) if hosts else ""}
  📻 Stream more vinyl sessions on Mixcloud:
  {MIXCLOUD_URL}

- Add a short “Featured styles” line using {", ".join(styles)} plus any clear styles you infer from the tracklist; end with “All vinyl.”
- Include a brief, professional copyright notice.
- Finish with 8–12 relevant hashtags (mix of general and style-specific; no duplicates).

# Tone & SEO
- Sophisticated, musical, and cinematic; no hype spam.
- Naturally include 2–3 primary styles in the body copy.
- Avoid repeating the title verbatim in the first line of the description.

# Constraints
- Do not fabricate tracks, artists, or years. Use only what’s listed in the tracklist.

# Output Format (MUST follow exactly)
TITLE:
<one line title>

DESCRIPTION:
<multi-line description, including the blocks and hashtags>
"""

def main():
    parser = argparse.ArgumentParser(description="Generate YouTube Title/Description prompt or a timestamped comment from MDX/YAML frontmatter")
    parser.add_argument("path", type=Path, help="Path to MDX/Markdown with YAML frontmatter, or a YAML file")
    parser.add_argument("--comment", action="store_true", help="Output a YouTube comment with timestamps from tracklist.duration_seconds")
    args = parser.parse_args()

    path = args.path
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    front = load_frontmatter(path)

    if args.comment:
        comment = build_youtube_comment(front.get("tracklist") or [])
        if not comment:
            print("No tracklist found or could not build comment.", file=sys.stderr)
            sys.exit(2)
        print(comment)
        return

    prompt = make_prompt(front)
    print(prompt)

if __name__ == "__main__":
    main()