#!/usr/bin/env python3
"""Publish one 52-at-52 run from a flat source folder.

The website root is fixed inside this script. Start the script with Python, enter
one race number, review the plan, and type PUBLISH to continue.

Expected source folder for Run 42:
  [website root]/content/new-runs/Run 42/

The folder contains data.txt, English and Portuguese Markdown story files, and
all photos/videos together. Media order is Gemini photos, then videos, then all
other photos.
"""
from __future__ import annotations

import copy
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

try:
    from PIL import Image, ImageOps
except ImportError:
    print("ERROR: Pillow is required. Install it once with: py -m pip install Pillow")
    raise SystemExit(1)

ROOT = Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
NEW_RUNS = ROOT / "content" / "new-runs"
POSTS_DIR = ROOT / "posts"
MEDIA_DIR = ROOT / "media"
DATA_DIR = ROOT / "data"
POSTS_JSON = ROOT / "posts.json"
RUN_IMAGES_JSON = ROOT / "run_images.json"
RUNS_JSON = DATA_DIR / "runs.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
STORY_EXTENSIONS = {".md", ".markdown", ".txt", ".html"}
MAX_IMAGE_EDGE = 2000
WEBP_QUALITY = 84
NA = "NA"


def ask_run_number() -> int:
    while True:
        value = input("Race number to publish (1-52, or Q to quit): ").strip()
        if value.casefold() in {"q", "quit", "exit"}:
            raise SystemExit(0)
        if value.isdigit() and 1 <= int(value) <= 52:
            return int(value)
        print("Please enter a whole number from 1 through 52.")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"Required website file was not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def atomic_write_json(path: Path, data: Any) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.stem}.backup-{timestamp}{path.suffix}")
    shutil.copy2(path, backup_path)
    return backup_path


def run_number_of(item: Any) -> int | None:
    if not isinstance(item, dict):
        return None
    for field in ("race", "run", "run_number", "number", "id"):
        try:
            return int(item.get(field))
        except (TypeError, ValueError):
            pass
    return None


def find_run_list(document: Any, filename: str) -> tuple[list[Any], Callable[[list[Any]], Any], str]:
    if isinstance(document, list):
        if document and not any(run_number_of(item) is not None for item in document):
            raise ValueError(f"{filename} is an array, but its entries do not contain run numbers.")
        return document, lambda updated: updated, "root array"
    if not isinstance(document, dict):
        raise ValueError(f"{filename} must be a JSON array or an object containing a list of run records.")
    options: list[tuple[str, list[Any]]] = []
    for key, value in document.items():
        if isinstance(value, list) and (not value or any(run_number_of(item) is not None for item in value)):
            options.append((key, value))
    if not options:
        raise ValueError(f"Cannot identify a run list inside {filename}; no files were changed.")
    preferred_keys = ("posts", "runs", "items", "data")
    key, records = next((option for option in options if option[0] in preferred_keys), options[0])

    def rebuild(updated: list[Any]) -> Any:
        result = copy.deepcopy(document)
        result[key] = updated
        return result

    return records, rebuild, f'object key "{key}"'


def find_image_map(document: Any) -> tuple[dict[str, Any], Callable[[dict[str, Any]], Any], str]:
    def looks_like_image_map(value: Any) -> bool:
        return isinstance(value, dict) and (not value or any(str(key).isdigit() for key in value))

    if looks_like_image_map(document):
        return document, lambda updated: updated, "root object"
    if not isinstance(document, dict):
        raise ValueError("run_images.json must be a JSON object; no files were changed.")
    for key in ("run_images", "images", "runs", "data"):
        nested = document.get(key)
        if looks_like_image_map(nested):
            def rebuild(updated: dict[str, Any], outer=document, nested_key=key) -> Any:
                result = copy.deepcopy(outer)
                result[nested_key] = updated
                return result
            return nested, rebuild, f'object key "{key}"'
    raise ValueError("Cannot identify a run-number image map inside run_images.json; no files were changed.")


def parse_data_txt(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required metadata file: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip().casefold()] = value.strip()
    return values


def find_story(source: Path, language: str) -> Path:
    files = [path for path in source.iterdir() if path.is_file() and path.suffix.lower() in STORY_EXTENSIONS and path.name.casefold() != "data.txt"]
    portuguese_terms = ("-pt", "_pt", "corrida", "portugues", "portuguese", "português")
    english_terms = ("-en", "_en", "run", "english", "ingles", "inglês")
    terms = portuguese_terms if language == "pt" else english_terms
    matches = [path for path in files if any(term in path.stem.casefold() for term in terms)]
    if language == "en":
        matches = [path for path in matches if not any(term in path.stem.casefold() for term in portuguese_terms)]
    if len(matches) != 1:
        description = ", ".join(path.name for path in matches) if matches else "none"
        raise ValueError(f"Expected exactly one {language.upper()} story file in {source.name}; found: {description}")
    return matches[0]


def parse_date(value: str) -> str:
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return value or NA


def number(value: str) -> float | str:
    if not value or value.strip().upper() == NA:
        return NA
    candidate = re.sub(r"[^0-9.]", "", value)
    try:
        return float(candidate)
    except ValueError:
        return NA


def duration_to_pace(duration: str, miles: float | str) -> str:
    if duration == NA or not isinstance(miles, float) or miles <= 0:
        return NA
    try:
        hours, minutes, seconds = [int(piece) for piece in duration.split(":")]
        total_seconds = hours * 3600 + minutes * 60 + seconds
        pace_seconds = round(total_seconds / miles)
        return f"{pace_seconds // 60}:{pace_seconds % 60:02d}"
    except ValueError:
        return NA


def first_nonempty_line(text: str, fallback: str) -> str:
    return next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip()), fallback)


def make_record(run: int, values: dict[str, str], english: str, portuguese: str) -> dict[str, Any]:
    miles = number(values.get("distance_miles", values.get("distance", "")))
    kilometers = number(values.get("distance_km", ""))
    if isinstance(miles, float) and kilometers == NA:
        kilometers = round(miles * 1.609344, 2)
    duration = values.get("duration", values.get("time", NA)) or NA
    pace = values.get("pace", values.get("pace_per_mile", "")) or duration_to_pace(duration, miles)
    company = [person.strip() for person in values.get("company", "").split("|") if person.strip()] or NA
    return {
        "race": run,
        "date": parse_date(values.get("date", "")),
        "miles": miles,
        "km": kilometers,
        "time": duration,
        "pace": pace,
        "shoes": values.get("shoes", NA) or NA,
        "where": values.get("location", values.get("where", NA)) or NA,
        "region": values.get("region", NA) or NA,
        "device": values.get("device", values.get("watch", NA)) or NA,
        "elevation_ft": number(values.get("elevation_ft", values.get("elevation", ""))),
        "audiobook": values.get("audiobook", NA) or NA,
        "company": company,
        "event_name": values.get("event_name", NA) or NA,
        "official_distance_km": number(values.get("official_distance_km", "")),
        "result": values.get("result", NA) or NA,
        "summary_en": values.get("summary_en", first_nonempty_line(english, f"Run #{run}")) or f"Run #{run}",
        "summary_pt": values.get("summary_pt", first_nonempty_line(portuguese, f"Corrida #{run}")) or f"Corrida #{run}",
    }


def youtube_id(url: str) -> str | None:
    parsed = urlparse(url.strip())
    hostname = parsed.netloc.casefold().removeprefix("www.")
    if hostname == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None
    if hostname in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        pieces = parsed.path.strip("/").split("/")
        if len(pieces) > 1 and pieces[0] in {"embed", "shorts"}:
            return pieces[1]
    return None


def inline_markdown(text: str) -> str:
    safe = html.escape(text, quote=False)
    safe = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', safe)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", safe)


def markdown_to_html(text: str) -> str:
    if re.search(r"<(h[1-6]|p|div|iframe|video)\b", text, flags=re.I):
        return text.strip() + "\n"
    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        item = block.strip()
        video = youtube_id(item)
        if video:
            blocks.append('<div class="video-embed"><iframe src="https://www.youtube-nocookie.com/embed/' + html.escape(video, quote=True) + '" title="YouTube video" loading="lazy" allowfullscreen></iframe></div>')
        elif item.startswith("### "):
            blocks.append(f"<h3>{inline_markdown(item[4:])}</h3>")
        elif item.startswith("## "):
            blocks.append(f"<h2>{inline_markdown(item[3:])}</h2>")
        elif item.startswith("# "):
            blocks.append(f"<h1>{inline_markdown(item[2:])}</h1>")
        else:
            blocks.append(f"<p>{inline_markdown(' '.join(line.strip() for line in item.splitlines()))}</p>")
    return "\n".join(blocks) + "\n"


def ordered_media(source: Path) -> list[Path]:
    all_media = [path for path in source.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS]

    def sort_key(path: Path) -> tuple[int, float, str]:
        is_image = path.suffix.lower() in IMAGE_EXTENSIONS
        if is_image and "gemini" in path.name.casefold():
            group = 0
        elif path.suffix.lower() in VIDEO_EXTENSIONS:
            group = 1
        else:
            group = 2
        return (group, path.stat().st_mtime, path.name.casefold())

    return sorted(all_media, key=sort_key)


def write_media(source: Path, target: Path) -> Path:
    if source.suffix.lower() in VIDEO_EXTENSIONS:
        shutil.copy2(source, target)
        return target
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
        should_keep_png = source.suffix.lower() == ".png" or "map" in source.stem.casefold()
        if should_keep_png:
            target = target.with_suffix(".png")
            if image.mode not in {"RGB", "RGBA", "L"}:
                image = image.convert("RGB")
            image.save(target, "PNG", optimize=True)
        else:
            target = target.with_suffix(".webp")
            if image.mode != "RGB":
                background = Image.new("RGB", image.size, "white")
                if image.mode == "RGBA":
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image)
                image = background
            image.save(target, "WEBP", quality=WEBP_QUALITY, method=6)
    return target


def replace_only_this_run(records: list[Any], run: int, record: dict[str, Any]) -> list[Any]:
    preserved = [item for item in records if run_number_of(item) != run]
    preserved.append(record)
    preserved.sort(key=lambda item: (run_number_of(item) is None, run_number_of(item) or 0))
    return preserved


def numeric_key_order(data: dict[str, Any]) -> dict[str, Any]:
    return {str(key): data[key] for key in sorted(data, key=lambda key: int(key) if str(key).isdigit() else 10**9)}


def main() -> None:
    print(f"Website folder: {ROOT}")
    if not ROOT.is_dir():
        raise FileNotFoundError(f"The fixed website folder does not exist: {ROOT}")
    run = ask_run_number()
    source = NEW_RUNS / f"Run {run}"
    if not source.is_dir():
        raise FileNotFoundError(f"Source folder does not exist: {source}")

    values = parse_data_txt(source / "data.txt")
    english_file = find_story(source, "en")
    portuguese_file = find_story(source, "pt")
    english_text = english_file.read_text(encoding="utf-8-sig")
    portuguese_text = portuguese_file.read_text(encoding="utf-8-sig")
    record = make_record(run, values, english_text, portuguese_text)
    media = ordered_media(source)
    if not media:
        raise ValueError(f"No photo or video files were found in {source}")

    posts_document = read_json(POSTS_JSON)
    images_document = read_json(RUN_IMAGES_JSON)
    post_records, rebuild_posts, posts_structure = find_run_list(posts_document, "posts.json")
    image_map, rebuild_images, images_structure = find_image_map(images_document)
    existing_numbers = sorted({number for number in (run_number_of(item) for item in post_records) if number is not None})

    print(f"Current runs in posts.json: {existing_numbers}")
    print(f"posts.json structure: {posts_structure}")
    print(f"run_images.json structure: {images_structure}")
    print(f"Adding or replacing only Run {run}. All other runs will remain unchanged.")
    print("Media sequence:")
    for index, file in enumerate(media, 1):
        print(f"  {index}. {file.name}")
    confirmation = input("Type PUBLISH to continue, or press Enter to cancel: ").strip()
    if confirmation != "PUBLISH":
        print("Cancelled. No files were changed.")
        return

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in (POSTS_JSON, RUN_IMAGES_JSON, RUNS_JSON):
        saved = backup(path)
        if saved:
            print(f"Backup created: {saved.name}")

    en_output = POSTS_DIR / f"run-{run:02d}-en.html"
    pt_output = POSTS_DIR / f"run-{run:02d}-pt.html"
    en_output.write_text(markdown_to_html(english_text), encoding="utf-8")
    pt_output.write_text(markdown_to_html(portuguese_text), encoding="utf-8")

    for old_media in MEDIA_DIR.glob(f"run{run:02d}_*"):
        old_media.unlink()
    created_media: list[str] = []
    for index, source_media in enumerate(media, 1):
        output_media = MEDIA_DIR / f"run{run:02d}_{index:03d}{source_media.suffix.lower()}"
        created_media.append(write_media(source_media, output_media).name)

    public_record = {key: record[key] for key in ("race", "date", "miles", "km", "time", "pace", "shoes", "where", "region", "summary_en", "summary_pt")}
    updated_posts = rebuild_posts(replace_only_this_run(post_records, run, public_record))
    updated_map = dict(image_map)
    updated_map[str(run)] = created_media
    updated_images = rebuild_images(numeric_key_order(updated_map))
    atomic_write_json(POSTS_JSON, updated_posts)
    atomic_write_json(RUN_IMAGES_JSON, updated_images)

    detailed_document = read_json(RUNS_JSON, {"schema_version": 1, "missing_value": NA, "runs": []})
    detail_records, rebuild_details, _ = find_run_list(detailed_document, "data/runs.json")
    detail_record = {
        "run_number": run,
        **{key: value for key, value in record.items() if key != "race"},
        "media": created_media,
        "content": {"en": f"posts/run-{run:02d}-en.html", "pt": f"posts/run-{run:02d}-pt.html"},
    }
    updated_details = rebuild_details(replace_only_this_run(detail_records, run, detail_record))
    if isinstance(updated_details, dict):
        updated_details["generated_at"] = datetime.now().isoformat(timespec="seconds")
        updated_details.setdefault("missing_value", NA)
    atomic_write_json(RUNS_JSON, updated_details)

    final_document = read_json(POSTS_JSON)
    final_records, _, _ = find_run_list(final_document, "posts.json")
    final_numbers = sorted({number for number in (run_number_of(item) for item in final_records) if number is not None})
    if run not in final_numbers:
        raise RuntimeError("Safety check failed: the selected run was not found after writing posts.json.")
    print(f"Success. posts.json now contains {len(final_numbers)} runs: {final_numbers}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. No further changes were made.")
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
