#!/usr/bin/env python3
"""52@52 one-time migration: clean post HTML and build a complete structured runs.json.

Run from the website root:
  python3 scripts/migrate_posts_to_json.py

What it does:
  - Backs up posts/ and existing JSON files.
  - Reads posts/run-XX-en.html and posts/run-XX-pt.html.
  - Removes old full-page wrappers, site navigation/header/footer, and run-stat tables
    from post fragments, keeping only the article text.
  - Builds data/runs.json with a record for every run found.
  - Keeps known values from posts.json and fills unavailable fields with "NA".
  - Does NOT overwrite posts.json or run_images.json.

Review data/runs.json afterward, especially fields marked "NA". The site can keep
using posts.json until the later index.html upgrade is ready.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing BeautifulSoup. Install it once with: python3 -m pip install beautifulsoup4")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DATA_DIR = ROOT / "data"
POSTS_JSON = ROOT / "posts.json"
OUTPUT_JSON = DATA_DIR / "runs.json"
NA = "NA"

FIELDS = [
    "run_number", "date", "location", "region", "distance_miles", "distance_km",
    "duration", "pace_per_mile", "elevation_ft", "device", "shoes", "audiobook",
    "company", "event_name", "official_distance_km", "result", "summary_en", "summary_pt"
]


def load_posts_metadata() -> dict[int, dict]:
    if not POSTS_JSON.exists():
        return {}
    try:
        items = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid posts.json: {exc}") from exc
    result = {}
    for item in items if isinstance(items, list) else []:
        try:
            result[int(item.get("race"))] = item
        except (TypeError, ValueError):
            continue
    return result


def text_or_na(value) -> str:
    if value is None:
        return NA
    value = str(value).strip()
    return value if value else NA


def value_from_label(text: str, labels: tuple[str, ...]) -> str | None:
    normalized = re.sub(r"\s+", " ", text).strip()
    for label in labels:
        match = re.search(rf"\b{re.escape(label)}\s*[:\-]\s*([^\n|]+)", normalized, re.I)
        if match:
            return match.group(1).strip()
    return None


def strip_non_article_html(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    root = soup.select_one(".article-body") or soup.body or soup

    for tag in root.select("script, style, noscript, header, footer, nav, .site-header, .language, .post-nav, .run-stats-grid, table, .facts"):
        tag.decompose()

    for tag in root.find_all(["a", "p", "div"]):
        label = tag.get_text(" ", strip=True).lower()
        href = (tag.get("href") or "").lower()
        if (
            href in {"../index.html", "index.html", "/"}
            or "52@52 — the year of the halves" in label
            or label in {"home", "all runs", "ler em português", "read in english"}
        ):
            tag.decompose()

    # Remove an old run-facts section even if it is plain text rather than a table.
    for tag in list(root.find_all(["p", "div", "section"])):
        text = tag.get_text(" ", strip=True).lower()
        fact_hits = sum(token in text for token in ("recorded distance", "official event distance", "elevation gain", "run details", "dados da corrida"))
        if fact_hits >= 2:
            tag.decompose()

    cleaned = root.decode_contents().strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned + "\n"


def title_from_html(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "html.parser")
    heading = soup.find(["h1", "h2"])
    return heading.get_text(" ", strip=True) if heading else NA


def build_record(run_number: int, meta: dict, en_html: str, pt_html: str) -> dict:
    miles = meta.get("miles", NA)
    km = meta.get("km", NA)
    time = meta.get("time", NA)
    pace = meta.get("pace", NA)
    company = meta.get("company", NA)
    if isinstance(company, list):
        company = company if company else NA
    elif not company:
        company = NA

    return {
        "run_number": run_number,
        "date": text_or_na(meta.get("date")),
        "location": text_or_na(meta.get("where")),
        "region": text_or_na(meta.get("region")),
        "distance_miles": miles if miles not in (None, "") else NA,
        "distance_km": km if km not in (None, "") else NA,
        "duration": text_or_na(time),
        "pace_per_mile": text_or_na(pace),
        "elevation_ft": meta.get("elevation_ft") if meta.get("elevation_ft") not in (None, "") else NA,
        "device": text_or_na(meta.get("device")),
        "shoes": text_or_na(meta.get("shoes")),
        "audiobook": text_or_na(meta.get("audiobook")),
        "company": company,
        "event_name": NA,
        "official_distance_km": NA,
        "result": NA,
        "summary_en": text_or_na(meta.get("summary_en")),
        "summary_pt": text_or_na(meta.get("summary_pt")),
        "content": {
            "en": {"file": f"posts/run-{run_number:02d}-en.html", "title": title_from_html(en_html)},
            "pt": {"file": f"posts/run-{run_number:02d}-pt.html", "title": title_from_html(pt_html)}
        }
    }


def ensure_run43(record: dict) -> None:
    if record["run_number"] != 43:
        return
    record.update({
        "date": "2026-08-30",
        "location": "Aracaju, Sergipe, Brazil",
        "region": "Sergipe, Brazil",
        "distance_miles": 15.25,
        "distance_km": 24.54,
        "duration": "02:27:13",
        "pace_per_mile": "9:39",
        "elevation_ft": NA,
        "device": "Pixel Watch 4",
        "shoes": "Altra Torin 8",
        "audiobook": "NA",
        "company": ["Paula Loures", "Mark Lee", "Jeff Bowers"],
        "event_name": "UMS – Ultramaratona Sergipe",
        "official_distance_km": 25,
        "result": "6th place, age category 50–59",
        "summary_en": "First official race of the 52@52 challenge: UMS Ultramaratona Sergipe 25K, with ocean, river, beach sand, heat, and a 6th-place age-category result.",
        "summary_pt": "Primeira prova oficial do desafio 52@52: UMS Ultramaratona Sergipe 25K, com mar, rio, areia de praia, calor e 6º lugar na categoria."
    })


def main() -> None:
    if not POSTS_DIR.is_dir():
        raise RuntimeError(f"Missing posts folder: {POSTS_DIR}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = ROOT / f"migration-backup-{stamp}"
    backup_posts = backup_dir / "posts"
    backup_dir.mkdir()
    shutil.copytree(POSTS_DIR, backup_posts)
    for src in (POSTS_JSON, OUTPUT_JSON):
        if src.exists():
            shutil.copy2(src, backup_dir / src.name)

    metadata = load_posts_metadata()
    pairs: dict[int, dict[str, Path]] = {}
    for file in POSTS_DIR.glob("run-*-*.html"):
        match = re.fullmatch(r"run-(\d+)-(en|pt)\.html", file.name, re.I)
        if match:
            number, language = int(match.group(1)), match.group(2).lower()
            pairs.setdefault(number, {})[language] = file

    if not pairs:
        raise RuntimeError("No posts/run-XX-en.html or posts/run-XX-pt.html files were found.")

    records = []
    cleaned_count = 0
    for number in sorted(pairs):
        pair = pairs[number]
        en_file = pair.get("en")
        pt_file = pair.get("pt")
        en_html = strip_non_article_html(en_file.read_text(encoding="utf-8")) if en_file else ""
        pt_html = strip_non_article_html(pt_file.read_text(encoding="utf-8")) if pt_file else ""
        if en_file:
            en_file.write_text(en_html, encoding="utf-8")
            cleaned_count += 1
        if pt_file:
            pt_file.write_text(pt_html, encoding="utf-8")
            cleaned_count += 1
        record = build_record(number, metadata.get(number, {}), en_html, pt_html)
        ensure_run43(record)
        records.append(record)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "missing_value": NA,
        "runs": records
    }
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Migration complete.")
    print(f"Backup folder: {backup_dir.name}")
    print(f"Cleaned post fragments: {cleaned_count}")
    print(f"Structured run records: {len(records)}")
    print("Created: data/runs.json")
    print("\nReview data/runs.json. Fields without reliable source data are set to 'NA'.")
    print("Your current site will continue reading posts.json and run_images.json until its next upgrade.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
