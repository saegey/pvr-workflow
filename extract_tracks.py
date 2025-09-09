#!/usr/bin/env python3
"""
extract_tracks.py

Extract selected fields from a JSON file containing track objects.

Usage:
  # Default (CSV to stdout)
  python extract_tracks.py -i /path/to/JAZZSAZON-3.json

  # YAML with default expanded fields
  python extract_tracks.py -i /path/to/JAZZSAZON-3.json --format yaml

  # YAML with only title+artist like your example
  python extract_tracks.py -i /path/to/JAZZSAZON-3.json --format yaml --fields title,artist

  # JSONL with custom fields
  python extract_tracks.py -i /path/to/JAZZSAZON-3.json --format jsonl --fields title,artist,album,year,bpm

  # Write to a file
  python extract_tracks.py -i /path/to/JAZZSAZON-3.json --format yaml -o tracklist.yaml
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, Dict, Any, List, Set

# Default expanded field set (you can override with --fields)
DEFAULT_FIELDS: List[str] = [
    # core
    "title", "artist", "album", "year",
    # context / curation
    "local_tags", "notes",
    # timing / key / bpm
    "duration", "duration_seconds", "key", "bpm",
    # positions / ids
    "track_id", "position", "id",
    # links / art
    "soundcloud_url", "discogs_url", "apple_music_url", "spotify_url", "youtube_url",
    "album_thumbnail",
    # misc
    "apple_music_persistent_id", "local_audio_url", "star_rating", "username",
    # collections (kept compact)
    "styles", "genres",
]

# Keys we never want to auto-include
BLACKLIST_KEYS: Set[str] = {
    "embedding"  # huge vectors—skip by default
}

def iter_records(data: Any) -> Iterable[Dict[str, Any]]:
    """
    Yield track-like dicts from:
    - a list of dicts
    - an object with 'tracks' list
    - a single dict
    """
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict):
        if "tracks" in data and isinstance(data["tracks"], list):
            for item in data["tracks"]:
                if isinstance(item, dict):
                    yield item
        else:
            yield data

def clean(value: Any) -> Any:
    """
    Normalize values for output:
    - None -> "" (for CSV/JSONL), None (for YAML we’ll stringify later)
    - simple types kept as-is
    - complex types (lists/dicts) kept as-is (CSV will JSON-encode)
    """
    return "" if value is None else value

def extract_row(track: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    return {k: clean(track.get(k, "")) for k in fields}

def all_fields_from_records(records: Iterable[Dict[str, Any]]) -> List[str]:
    seen: Set[str] = set()
    for r in records:
        for k in r.keys():
            if k not in BLACKLIST_KEYS:
                seen.add(k)
    # Keep a stable order: DEFAULT_FIELDS first (if present), then the rest sorted
    ordered = [k for k in DEFAULT_FIELDS if k in seen]
    ordered += sorted(seen - set(ordered))
    return ordered

def write_csv(rows: Iterable[Dict[str, Any]], output_path: Path, fields: List[str]) -> None:
    out_fh = sys.stdout if str(output_path) == "-" else output_path.open("w", newline="", encoding="utf-8")
    with out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            # JSON-encode lists/dicts so CSV stays 1 cell wide per field
            safe = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()}
            writer.writerow(safe)

def write_jsonl(rows: Iterable[Dict[str, Any]], output_path: Path) -> None:
    out_fh = sys.stdout if str(output_path) == "-" else output_path.open("w", encoding="utf-8")
    with out_fh:
        for r in rows:
            out_fh.write(json.dumps(r, ensure_ascii=False) + "\n")

def yaml_escape(s: str) -> str:
    """
    Very light YAML string escaper for our simple key: value use-case.
    Always double-quote and escape backslashes and quotes; preserves Unicode.
    """
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

def write_yaml(rows: List[Dict[str, Any]], output_path: Path, root_key: str = "tracklist") -> None:
    """
    Emit a compact YAML like:
    tracklist:
      - title: "Jazzy"
        artist: "Willie Colón, Hector Lavoe"
        ...
    No external dependencies required.
    """
    out_fh = sys.stdout if str(output_path) == "-" else output_path.open("w", encoding="utf-8")
    def dump_value(v: Any, indent: int) -> str:
        sp = " " * indent
        if isinstance(v, str):
            return yaml_escape(v)
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None or v == "":
            return '""'
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            if not v:
                return "[]"
            # block list
            lines = []
            for item in v:
                if isinstance(item, (dict, list)):
                    # nested complex—indent on next line
                    lines.append("\n" + sp + "- " + dump_value(item, indent + 2).lstrip())
                else:
                    lines.append("\n" + sp + "- " + dump_value(item, indent + 2))
            return "".join(lines)
        if isinstance(v, dict):
            if not v:
                return "{}"
            lines = []
            for kk, vv in v.items():
                lines.append(f"\n{sp}{kk}: {dump_value(vv, indent + 2)}")
            return "".join(lines)
        # fallback stringify
        return yaml_escape(str(v))

    with out_fh:
        out_fh.write(f"{root_key}:\n")
        for row in rows:
            out_fh.write("  -")
            first = True
            for k, v in row.items():
                # newline + two spaces + key: value
                out_fh.write(("\n" if first else "\n") + f"    {k}: {dump_value(v, 6)}")
                first = False
            out_fh.write("\n")

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract track fields from a JSON file.")
    parser.add_argument("-i", "--input", required=True, help="Path to input JSON file.")
    parser.add_argument("-o", "--output", default="-", help="Path to output file (default: stdout).")
    parser.add_argument(
        "--format",
        choices=["csv", "jsonl", "yaml"],
        default="csv",
        help="Output format. Default: csv",
    )
    parser.add_argument(
        "--fields",
        help="Comma-separated list of fields to include (overrides defaults). Example: title,artist,album,year",
    )
    parser.add_argument(
        "--yaml-root-name",
        default="tracklist",
        help='Root key name for YAML output (default: "tracklist").',
    )
    parser.add_argument(
        "--all-fields",
        action="store_true",
        help="Infer all available fields from the data (minus large/blacklisted ones)."
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    try:
        with in_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON ({e})", file=sys.stderr)
        sys.exit(1)

    # Load records to a list (we may need to inspect for --all-fields or iterate twice)
    records = list(iter_records(data))

    # Decide field list
    if args.all_fields:
        fields = all_fields_from_records(records)
    elif args.fields:
        fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    else:
        fields = DEFAULT_FIELDS

    # Build rows
    rows = [extract_row(t, fields) for t in records]

    # Write
    if args.format == "csv":
        write_csv(rows, out_path, fields)
    elif args.format == "jsonl":
        write_jsonl(rows, out_path)
    else:  # yaml
        write_yaml(rows, out_path, root_key=args.yaml_root_name)

if __name__ == "__main__":
    main()