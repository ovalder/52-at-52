#!/usr/bin/env python3
"""Remove one slideshow item from an already-published 52@52 run.

The website root is fixed, so this script can be started from any folder.
It asks for only:
  1. The published run number.
  2. The slideshow position to remove (starting at 1).

It updates only that run's entry in run_images.json and moves the removed file
from media/ to media/removed/Run-NN/ instead of deleting it permanently.

Run:
  py C:/Users/valde/OneDrive/Documents/52-at-52/scripts/remove_run_media.py
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
MEDIA_DIR = ROOT / "media"
REMOVED_DIR = MEDIA_DIR / "removed"
RUN_IMAGES_JSON = ROOT / "run_images.json"


def ask_number(prompt: str, minimum: int, maximum: int) -> int:
    while True:
        value = input(prompt).strip()
        if value.casefold() in {"q", "quit", "exit"}:
            raise SystemExit(0)
        if value.isdigit() and minimum <= int(value) <= maximum:
            return int(value)
        print(f"Please enter a whole number from {minimum} through {maximum}, or Q to quit.")


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


def normalize_media_name(value: Any) -> str:
    return str(value).replace("\\", "/").removeprefix("./").removeprefix("media/")


def resolve_media_file(name: str) -> Path:
    candidate = (MEDIA_DIR / name).resolve()
    media_root = MEDIA_DIR.resolve()
    if candidate != media_root and media_root not in candidate.parents:
        raise ValueError(f"Unsafe media filename in run_images.json: {name}")
    return candidate


def describe_item(position: int, name: str) -> str:
    extension = Path(name).suffix.lower()
    media_type = "VIDEO" if extension in {".mp4", ".webm", ".mov", ".m4v"} else "PHOTO"
    return f"{position}. [{media_type}] {name}"


def main() -> None:
    print(f"Website folder: {ROOT}")
    if not ROOT.is_dir():
        raise FileNotFoundError(f"The website folder does not exist: {ROOT}")

    image_map = read_json(RUN_IMAGES_JSON)
    published_runs = sorted(int(key) for key, value in image_map.items() if str(key).isdigit() and isinstance(value, list))
    if not published_runs:
        raise ValueError("run_images.json contains no published run media lists.")

    run = ask_number("Published run number to remove media from (1-52, or Q to quit): ", 1, 52)
    run_key = str(run)
    if run_key not in image_map or not isinstance(image_map[run_key], list) or not image_map[run_key]:
        available = ", ".join(str(number) for number in published_runs)
        raise ValueError(f"Run {run} has no slideshow items. Published runs with media: {available}")

    items = [normalize_media_name(item) for item in image_map[run_key]]
    print(f"\nRun {run} slideshow items:")
    for position, name in enumerate(items, start=1):
        print("  " + describe_item(position, name))

    item_position = ask_number(
        f"Item position to remove (1-{len(items)}, or Q to quit): ",
        1,
        len(items),
    )
    removed_name = items[item_position - 1]
    source_file = resolve_media_file(removed_name)

    print(f"\nSelected for removal: {describe_item(item_position, removed_name)}")
    if source_file.exists():
        print(f"File will be moved to: media/removed/Run-{run:02d}/{source_file.name}")
    else:
        print("The file is already missing from media/. The slideshow entry can still be removed.")

    answer = input("Type REMOVE to update the slideshow, or press Enter to cancel: ").strip()
    if answer != "REMOVE":
        print("Cancelled. No files were changed.")
        return

    saved_backup = backup(RUN_IMAGES_JSON)
    archived_file: Path | None = None
    if source_file.exists():
        archive_folder = REMOVED_DIR / f"Run-{run:02d}"
        archive_folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_target = archive_folder / source_file.name
        if archive_target.exists():
            archive_target = archive_folder / f"{source_file.stem}-{timestamp}{source_file.suffix}"
        shutil.move(str(source_file), str(archive_target))
        archived_file = archive_target

    image_map[run_key] = items[: item_position - 1] + items[item_position:]
    image_map = {
        str(key): image_map[key]
        for key in sorted(image_map, key=lambda key: int(key) if str(key).isdigit() else 10**9)
    }
    atomic_write_json(RUN_IMAGES_JSON, image_map)

    verify = read_json(RUN_IMAGES_JSON)
    remaining = [normalize_media_name(item) for item in verify.get(run_key, [])]
    if removed_name in remaining:
        raise RuntimeError("Safety check failed: the selected slideshow item is still present in run_images.json.")

    print(f"Success. Removed slideshow item #{item_position} from Run {run}.")
    print(f"Updated: {RUN_IMAGES_JSON}")
    print(f"Backup: {saved_backup.name}")
    if archived_file:
        print(f"Moved, not deleted: {archived_file}")
    else:
        print("No source media file was moved because it was already absent from media/.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. No further changes were made.")
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
