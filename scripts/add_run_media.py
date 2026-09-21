#!/usr/bin/env python3
"""Add new photos or videos to an already-published 52@52 run.

The website location is fixed, so this script can be run from any folder.
It only updates media/runNN_* files and the selected key in run_images.json.
It does NOT modify posts.json, the written story, or any other run.

Put only the NEW media files in:
  C:/Users/valde/OneDrive/Documents/52-at-52/content/new-runs/Run 44-add/

Then run:
  py C:/Users/valde/OneDrive/Documents/52-at-52/scripts/add_run_media.py

The script asks for the published run number and appends the new files after
existing slideshow items by default. Add the word Gemini to a new photo's
filename to place it before all other slideshow media for that run.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageOps
except ImportError:
    print("ERROR: Pillow is required. Install it once with: py -m pip install Pillow")
    raise SystemExit(1)

ROOT = Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
NEW_RUNS_DIR = ROOT / "content" / "new-runs"
MEDIA_DIR = ROOT / "media"
RUN_IMAGES_JSON = ROOT / "run_images.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
MAX_IMAGE_EDGE = 2000
WEBP_QUALITY = 84


def ask_run_number() -> int:
    while True:
        value = input("Published run number to add media to (1-52, or Q to quit): ").strip()
        if value.casefold() in {"q", "quit", "exit"}:
            raise SystemExit(0)
        if value.isdigit() and 1 <= int(value) <= 52:
            return int(value)
        print("Please enter a whole number from 1 through 52.")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required website file was not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected {path.name} to contain a JSON object.")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")
    shutil.copy2(path, target)
    return target


def extension_is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def extension_is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def source_folder_for(run: int) -> Path:
    """Accept several clear folder names for a media-only addition."""
    options = [
        NEW_RUNS_DIR / f"Run {run}-add",
        NEW_RUNS_DIR / f"Run {run} add",
        NEW_RUNS_DIR / f"Run {run} - add media",
        NEW_RUNS_DIR / f"Run {run} media",
    ]
    found = [path for path in options if path.is_dir()]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        names = ", ".join(path.name for path in found)
        raise ValueError(f"More than one addition folder exists for Run {run}: {names}. Keep only one.")
    raise FileNotFoundError(
        "No media-only source folder was found. Create exactly this folder and put only new photos/videos inside it:\n"
        f"  {NEW_RUNS_DIR / f'Run {run}-add'}"
    )


def collect_media(folder: Path) -> list[Path]:
    media = [p for p in folder.iterdir() if p.is_file() and (extension_is_image(p) or extension_is_video(p))]
    if not media:
        raise ValueError(f"No supported media found in {folder}. Supported: JPG, JPEG, PNG, WEBP, MP4, WEBM, MOV, M4V.")

    def key(path: Path) -> tuple[int, float, str]:
        if extension_is_image(path) and "gemini" in path.name.casefold():
            group = 0
        elif extension_is_video(path):
            group = 1
        else:
            group = 2
        return (group, path.stat().st_mtime, path.name.casefold())

    return sorted(media, key=key)


def existing_media_number(names: list[str], run: int) -> int:
    highest = 0
    pattern = re.compile(rf"^run{run:02d}_(\d+)", re.IGNORECASE)
    for name in names:
        match = pattern.match(Path(str(name)).name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def write_image(source: Path, target: Path) -> Path:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
        keep_png = source.suffix.lower() == ".png" or "map" in source.stem.casefold()
        if keep_png:
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


def output_media(source: Path, run: int, number: int) -> Path:
    target = MEDIA_DIR / f"run{run:02d}_{number:03d}{source.suffix.lower()}"
    if extension_is_video(source):
        shutil.copy2(source, target)
        return target
    return write_image(source, target)


def is_gemini_name(name: str) -> bool:
    return "gemini" in name.casefold()


def main() -> None:
    print(f"Website folder: {ROOT}")
    if not ROOT.is_dir():
        raise FileNotFoundError(f"The website folder does not exist: {ROOT}")
    if not RUN_IMAGES_JSON.exists():
        raise FileNotFoundError(f"The website image map does not exist: {RUN_IMAGES_JSON}")

    run = ask_run_number()
    source = source_folder_for(run)
    additions = collect_media(source)
    image_map = read_json(RUN_IMAGES_JSON)
    key = str(run)
    if key not in image_map or not isinstance(image_map[key], list):
        raise ValueError(f"Run {run} is not already present in run_images.json. Use the normal publish script for a new run.")

    existing = [str(item).replace("\\", "/").removeprefix("media/") for item in image_map[key]]
    next_number = existing_media_number(existing, run) + 1

    print(f"Source folder: {source}")
    print(f"Existing slideshow items for Run {run}: {len(existing)}")
    print("New media to add:")
    for index, item in enumerate(additions, start=next_number):
        kind = "VIDEO" if extension_is_video(item) else "PHOTO"
        first = " — Gemini priority" if is_gemini_name(item.name) and extension_is_image(item) else ""
        print(f"  {index:03d}. [{kind}] {item.name}{first}")

    answer = input("Type ADD to copy these files and update only this run's slideshow, or press Enter to cancel: ").strip()
    if answer != "ADD":
        print("Cancelled. No files were changed.")
        return

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    saved_backup = backup(RUN_IMAGES_JSON)
    created: list[str] = []
    for offset, item in enumerate(additions):
        created_path = output_media(item, run, next_number + offset)
        created.append(created_path.name)

    # Gemini-labelled additions are intentionally placed first. Other additions
    # are appended, preserving the order and all existing published media.
    gemini_additions = [name for item, name in zip(additions, created) if extension_is_image(item) and is_gemini_name(item.name)]
    normal_additions = [name for item, name in zip(additions, created) if name not in gemini_additions]
    image_map[key] = gemini_additions + existing + normal_additions
    image_map = {str(k): image_map[k] for k in sorted(image_map, key=lambda k: int(k) if str(k).isdigit() else 10**9)}
    atomic_write_json(RUN_IMAGES_JSON, image_map)

    verify = read_json(RUN_IMAGES_JSON)
    saved = verify.get(key, [])
    if not all(name in saved for name in created):
        raise RuntimeError("Safety check failed: one or more new media filenames were not saved to run_images.json.")

    print(f"Success. Added {len(created)} file(s) to Run {run}.")
    print(f"Updated: {RUN_IMAGES_JSON}")
    print(f"Backup: {saved_backup.name}")
    print("The source files are left in the -add folder, so they can be kept as your original copies.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. No further changes were made.")
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
