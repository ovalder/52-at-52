#!/usr/bin/env python3
"""Add/correct Run 43 in an existing complete 52@52 posts.json and run_images.json.

Save this file in the website root (beside posts.json and run_images.json), then run:
  python3 add_run43_to_existing_data.py

It creates backups and preserves Runs 1–41. It does not create image files;
Run 43 image entries are added only for files that currently exist in media/.
"""
from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import sys

root = Path(__file__).resolve().parent
posts_path = root / "posts.json"
images_path = root / "run_images.json"
media_dir = root / "media"

for path in (posts_path, images_path):
    if not path.exists():
        sys.exit(f"ERROR: Missing {path.name} beside this script. No changes were made.")

try:
    posts = json.loads(posts_path.read_text(encoding="utf-8"))
    image_map = json.loads(images_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    sys.exit(f"ERROR: Invalid JSON: {exc}")

if not isinstance(posts, list):
    sys.exit("ERROR: posts.json must contain a JSON array.")
if not isinstance(image_map, dict):
    sys.exit("ERROR: run_images.json must contain a JSON object.")

backup_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(posts_path, root / f"posts.before-run43-{backup_stamp}.json")
shutil.copy2(images_path, root / f"run_images.before-run43-{backup_stamp}.json")

run43 = {
    "race": 43,
    "date": "2026-08-30",
    "miles": 15.25,
    "km": 24.54,
    "time": "02:27:13",
    "pace": "9:39",
    "shoes": "Altra Torin 8",
    "where": "Aracaju, Sergipe, Brazil",
    "region": "Sergipe, Brazil",
    "device": "Pixel Watch 4",
    "elevation_ft": None,
    "audiobook": None,
    "company": ["Paula Loures", "Mark Lee", "Jeff Bowers"],
    "summary_en": "First official race of the 52@52 challenge: UMS Ultramaratona Sergipe 25K, with ocean, river, beach sand, heat, and a 6th-place age-category result.",
    "summary_pt": "Primeira prova oficial do desafio 52@52: UMS Ultramaratona Sergipe 25K, com mar, rio, areia de praia, calor e 6º lugar na categoria."
}

posts = [item for item in posts if int(item.get("race", -1)) != 43]
posts.append(run43)
posts.sort(key=lambda item: int(item.get("race", 0)))
posts_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if media_dir.exists():
    found = sorted(
        p.name for p in media_dir.iterdir()
        if p.is_file() and re.fullmatch(r"run43_\d{3}\.(webp|png|jpe?g)", p.name, re.IGNORECASE)
    )
else:
    found = []

if found:
    image_map["43"] = found
    image_note = f"Added {len(found)} existing Run 43 image(s) from media/."
elif "43" not in image_map:
    image_map["43"] = []
    image_note = "Added an empty Run 43 image list because no media/run43_001.webp-style files were found."
else:
    image_note = "Kept your existing Run 43 image list because no matching files were found in media/."

ordered_images = {str(key): image_map[key] for key in sorted(image_map, key=lambda value: int(value))}
images_path.write_text(json.dumps(ordered_images, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("Done.")
print("Updated posts.json while preserving all existing runs.")
print("Updated run_images.json.")
print(image_note)
print("\nBackups created:")
print(f"  posts.before-run43-{backup_stamp}.json")
print(f"  run_images.before-run43-{backup_stamp}.json")
print("\nMake sure these article files exist:")
print("  posts/run-43-en.html")
print("  posts/run-43-pt.html")
