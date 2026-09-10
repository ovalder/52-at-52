#!/usr/bin/env python3
"""Publish one 52@52 run into the existing single-page static site.

Run from the website root:
  python3 scripts/publish_run.py

Required source folder:
  incoming-runs/run-44/
    metadata.txt
    run-en.md
    run-pt.md
    images/

The script creates or replaces posts/run-XX-en.html and posts/run-XX-pt.html,
optimizes copies of images into media/, and updates posts.json and run_images.json.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Missing Pillow. Install it once with: python3 -m pip install Pillow")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
INCOMING = ROOT / "incoming-runs"
POSTS_DIR = ROOT / "posts"
MEDIA_DIR = ROOT / "media"
POSTS_JSON = ROOT / "posts.json"
IMAGES_JSON = ROOT / "run_images.json"
MAX_EDGE = 2000
WEBP_QUALITY = 84
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def read_metadata(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip()
    return data


def required(meta: dict[str, str], key: str) -> str:
    value = meta.get(key, "").strip()
    if not value:
        raise ValueError(f"metadata.txt is missing required field: {key}")
    return value


def parse_date(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("date must be YYYY-MM-DD, Aug 30, 2026, August 30, 2026, or MM/DD/YYYY")


def parse_float(value: str, field: str) -> float:
    cleaned = re.sub(r"[^0-9.]", "", value)
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field} must contain a number") from exc


def duration_seconds(value: str) -> int:
    parts = value.strip().split(":")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError("duration must use HH:MM:SS, for example 02:27:13")
    h, m, s = map(int, parts)
    if m > 59 or s > 59:
        raise ValueError("duration has invalid minutes or seconds")
    return h * 3600 + m * 60 + s


def pace_from(duration: str, miles: float) -> str:
    seconds = round(duration_seconds(duration) / miles)
    return f"{seconds // 60}:{seconds % 60:02d}"


def youtube_id(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = parsed.netloc.lower().replace("www.", "")
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None
    if host in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/"):
            return parsed.path.strip("/").split("/")[1]
    return None


def inline_markdown(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" loading="lazy">', escaped)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def markdown_to_html(markdown_text: str) -> str:
    blocks = re.split(r"\n\s*\n", markdown_text.strip())
    output: list[str] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]
        compact = "\n".join(lines).strip()
        if not compact:
            continue
        video = youtube_id(compact)
        if video:
            output.append(
                '<div class="video-embed"><iframe src="https://www.youtube-nocookie.com/embed/'
                + html.escape(video, quote=True)
                + '" title="YouTube video" loading="lazy" referrerpolicy="strict-origin-when-cross-origin" '
                'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div>'
            )
            continue
        if compact.startswith("### "):
            output.append(f"<h3>{inline_markdown(compact[4:])}</h3>")
        elif compact.startswith("## "):
            output.append(f"<h2>{inline_markdown(compact[3:])}</h2>")
        elif compact.startswith("# "):
            output.append(f"<h1>{inline_markdown(compact[2:])}</h1>")
        elif all(line.lstrip().startswith(('- ', '* ')) for line in lines if line.strip()):
            items = ''.join(f"<li>{inline_markdown(line.strip()[2:])}</li>" for line in lines if line.strip())
            output.append(f"<ul>{items}</ul>")
        elif all(re.match(r"\d+\.\s+", line.lstrip()) for line in lines if line.strip()):
            items = ''.join(f"<li>{inline_markdown(re.sub(r'^\d+\.\s+', '', line.strip()))}</li>" for line in lines if line.strip())
            output.append(f"<ol>{items}</ol>")
        else:
            paragraph = " ".join(line.strip() for line in lines)
            output.append(f"<p>{inline_markdown(paragraph)}</p>")
    return "\n".join(output) + "\n"


def optimize_images(images_dir: Path, run_number: int) -> list[str]:
    if not images_dir.is_dir():
        raise ValueError(f"Missing images folder: {images_dir}")
    source_files = sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    if not source_files:
        raise ValueError(f"No JPG, JPEG, PNG, or WebP images found in {images_dir}")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for i, source in enumerate(source_files, start=1):
        try:
            with Image.open(source) as im:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
                is_graphic = source.suffix.lower() == ".png" and ("map" in source.stem.lower() or im.mode in {"RGBA", "LA"})
                if is_graphic:
                    filename = f"run{run_number:02d}_{i:03d}.png"
                    destination = MEDIA_DIR / filename
                    if im.mode not in {"RGB", "RGBA", "L"}:
                        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
                    im.save(destination, "PNG", optimize=True)
                else:
                    filename = f"run{run_number:02d}_{i:03d}.webp"
                    destination = MEDIA_DIR / filename
                    if im.mode != "RGB":
                        background = Image.new("RGB", im.size, "white")
                        if im.mode == "RGBA":
                            background.paste(im, mask=im.getchannel("A"))
                        else:
                            background.paste(im)
                        im = background
                    im.save(destination, "WEBP", quality=WEBP_QUALITY, method=6)
                names.append(filename)
                print(f"  image: {source.name} -> media/{filename} ({im.width}x{im.height})")
        except Exception as exc:
            raise ValueError(f"Could not process image {source.name}: {exc}") from exc
    return names


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path.name}: {exc}") from exc


def update_posts(meta: dict[str, str], run_number: int, date: str, miles: float, km: float, duration: str, pace: str) -> None:
    posts = load_json(POSTS_JSON, [])
    if not isinstance(posts, list):
        raise ValueError("posts.json must contain a JSON array")
    record = {
        "race": run_number,
        "date": date,
        "miles": round(miles, 2),
        "km": round(km, 2),
        "time": duration,
        "pace": pace,
        "shoes": required(meta, "shoes"),
        "where": required(meta, "location"),
        "region": meta.get("region", ""),
        "device": meta.get("device", meta.get("watch", "")),
        "elevation_ft": parse_float(meta["elevation_ft"], "elevation_ft") if meta.get("elevation_ft") else None,
        "audiobook": meta.get("audiobook") or None,
        "company": [x.strip() for x in meta.get("company", "").split("|") if x.strip()],
        "summary_en": meta.get("summary_en", ""),
        "summary_pt": meta.get("summary_pt", ""),
    }
    posts = [p for p in posts if int(p.get("race", -1)) != run_number]
    posts.append(record)
    posts.sort(key=lambda p: int(p.get("race", 0)))
    POSTS_JSON.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_images(run_number: int, image_names: list[str]) -> None:
    image_map = load_json(IMAGES_JSON, {})
    if not isinstance(image_map, dict):
        raise ValueError("run_images.json must contain a JSON object")
    image_map[str(run_number)] = image_names
    ordered = {str(k): image_map[k] for k in sorted(image_map, key=lambda x: int(x))}
    IMAGES_JSON.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    print("52@52 run publisher\n")
    folder_name = input("New-run folder inside incoming-runs (example: run-44): ").strip()
    source = Path(folder_name)
    if not source.is_absolute():
        source = INCOMING / folder_name
    source = source.resolve()
    if not source.is_dir():
        raise ValueError(f"Folder not found: {source}")

    meta = read_metadata(source / "metadata.txt")
    run_number = int(required(meta, "run"))
    date = parse_date(required(meta, "date"))
    miles = parse_float(required(meta, "distance_miles"), "distance_miles")
    km = parse_float(meta.get("distance_km", ""), "distance_km") if meta.get("distance_km") else miles * 1.609344
    duration = required(meta, "duration")
    pace = pace_from(duration, miles)
    en_file = source / "run-en.md"
    pt_file = source / "run-pt.md"
    if not en_file.exists() or not pt_file.exists():
        raise ValueError("Both run-en.md and run-pt.md are required")

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    print("\nProcessing images:")
    image_names = optimize_images(source / "images", run_number)

    (POSTS_DIR / f"run-{run_number:02d}-en.html").write_text(markdown_to_html(en_file.read_text(encoding="utf-8")), encoding="utf-8")
    (POSTS_DIR / f"run-{run_number:02d}-pt.html").write_text(markdown_to_html(pt_file.read_text(encoding="utf-8")), encoding="utf-8")
    update_posts(meta, run_number, date, miles, km, duration, pace)
    update_images(run_number, image_names)

    print("\nPublished locally:")
    print(f"  posts/run-{run_number:02d}-en.html")
    print(f"  posts/run-{run_number:02d}-pt.html")
    print("  posts.json")
    print("  run_images.json")
    print(f"  {len(image_names)} optimized image(s) in media/")
    print(f"  calculated pace: {pace} /mi")
    print("\nTest from the site root with: python3 -m http.server 8000")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}")
        sys.exit(1)
