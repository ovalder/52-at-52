#!/usr/bin/env python3
"""Safely archive unused or historical files from the 52@52 website.

The website root is fixed:
  C:/Users/valde/OneDrive/Documents/52-at-52

This script never deletes files. It first scans and writes a report. If you
choose to proceed, it moves selected candidates into one timestamped folder in
the website root and writes log.txt with every original and archive location.

It protects files currently referenced by run_images.json and index.html, all
current website content, all source folders under content/new-runs/Run N, and
all required project files. It only auto-selects clearly archival files:
  - *.backup-YYYYMMDD-HHMMSS.*
  - index_backup.html and other explicitly named backup copies
  - old copies in assets/images/run-*/ (legacy source-media archive)
  - old data/ posts.json and run_images.json only when the active root versions exist
  - old publisher scripts and publishing guides in content/new-runs/

The archive keeps the original folder layout, so files are easy to restore.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
MEDIA_DIR = ROOT / "media"
RUN_IMAGES_JSON = ROOT / "run_images.json"
POSTS_JSON = ROOT / "posts.json"
INDEX_HTML = ROOT / "index.html"
ARCHIVE_PREFIX = "backup-unused-files-"

BACKUP_NAME = re.compile(r"\.backup-\d{8}-\d{6}(?:\.[^.]+)?$", re.IGNORECASE)
EXPLICIT_BACKUP = re.compile(r"(^|[_-])(backup|old|copy)([_-]|$)", re.IGNORECASE)
MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mov", ".m4v"}
TEXT_EXTENSIONS = {".html", ".htm", ".css", ".js", ".json", ".md", ".txt", ".xml", ".yml", ".yaml"}


def read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file was not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def files_referenced_by_run_images() -> set[str]:
    data = read_json(RUN_IMAGES_JSON)
    if not isinstance(data, dict):
        raise ValueError("run_images.json must contain an object keyed by run number.")
    referenced = set()
    for values in data.values():
        if not isinstance(values, list):
            continue
        for value in values:
            name = str(value).replace("\\", "/").removeprefix("./").removeprefix("media/")
            referenced.add((MEDIA_DIR / name).resolve().as_posix().casefold())
    return referenced


def text_references() -> set[str]:
    """Find direct local media references in current site text files."""
    references: set[str] = set()
    pattern = re.compile(r"(?:src|href)=[\"']([^\"']+)[\"']", re.IGNORECASE)
    files = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS]
    for path in files:
        if any(part.startswith(ARCHIVE_PREFIX) for part in path.relative_to(ROOT).parts):
            continue
        if is_inside(path, ROOT / ".git"):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw in pattern.findall(content):
            if raw.startswith(("http://", "https://", "#", "data:", "mailto:", "javascript:")):
                continue
            target = raw.split("?", 1)[0].split("#", 1)[0].replace("/", "\\")
            if not target:
                continue
            candidate = (path.parent / target).resolve()
            if candidate.exists() and is_inside(candidate, ROOT):
                references.add(candidate.as_posix().casefold())
    return references


def protected(path: Path, slideshow_refs: set[str], html_refs: set[str]) -> bool:
    resolved = path.resolve()
    lower = resolved.as_posix().casefold()
    parts = resolved.relative_to(ROOT.resolve()).parts
    if lower in slideshow_refs or lower in html_refs:
        return True
    if path in {RUN_IMAGES_JSON, POSTS_JSON, INDEX_HTML}:
        return True
    if path.name in {"logo.png", ".gitignore", ".gitattributes"}:
        return True
    if ".git" in parts:
        return True
    if "scripts" in parts:
        return True
    if "content" in parts and "new-runs" in parts:
        # Keep all current source materials, templates, and media-only addition folders.
        return True
    if "posts" in parts or "summaries" in parts or "tips" in parts or "guides" in parts:
        return True
    if path.parent == ROOT and path.suffix.lower() in {".md", ".json", ".html"} and not BACKUP_NAME.search(path.name):
        return True
    return False


def reason_for_archive(path: Path) -> str | None:
    relative = rel(path)
    name = path.name
    if BACKUP_NAME.search(name):
        return "Timestamped automatic backup"
    if name.casefold() == "index_backup.html":
        return "Named backup of index.html"
    if is_inside(path, ROOT / "assets" / "images"):
        return "Legacy source-media archive (not used by current slideshow map)"
    if path == ROOT / "data" / "posts.json" and POSTS_JSON.exists():
        return "Legacy data/posts.json; active file is root posts.json"
    if path == ROOT / "data" / "run_images.json" and RUN_IMAGES_JSON.exists():
        return "Legacy data/run_images.json; active file is root run_images.json"
    if path.parent == ROOT / "content" / "new-runs" and name in {"publish_run_OLD.py", "run-publishing-guide.md"}:
        return "Superseded publishing material"
    if "_backup" in name.casefold() or EXPLICIT_BACKUP.search(path.stem):
        return "Explicitly named backup/copy"
    return None


def candidate_files(slideshow_refs: set[str], html_refs: set[str]) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(ROOT).parts
        if any(part.startswith(ARCHIVE_PREFIX) for part in relative_parts):
            continue
        if protected(path, slideshow_refs, html_refs):
            continue
        reason = reason_for_archive(path)
        if reason:
            candidates.append((path, reason))
    return sorted(candidates, key=lambda item: rel(item[0]).casefold())


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def write_report(folder: Path, candidates: list[tuple[Path, str]], moved: list[tuple[str, str, str, int]] | None = None) -> Path:
    report = folder / "log.txt"
    total = sum(path.stat().st_size for path, _ in candidates if path.exists()) if moved is None else sum(size for _, _, _, size in moved)
    lines = [
        "52@52 Website Cleanup Log",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        f"Website root: {ROOT}",
        "",
    ]
    if moved is None:
        lines += [
            "MODE: PREVIEW ONLY — no files were moved.",
            f"Candidates: {len(candidates)} file(s), {format_size(total)} total.",
            "",
            "Candidate files:",
        ]
        for path, reason in candidates:
            lines += [f"SOURCE: {path}", f"REASON: {reason}", f"SIZE: {path.stat().st_size} bytes", ""]
    else:
        lines += [
            "MODE: FILES MOVED TO THIS ARCHIVE FOLDER.",
            f"Moved: {len(moved)} file(s), {format_size(total)} total.",
            "",
            "Moved files:",
        ]
        for source, destination, reason, size in moved:
            lines += [f"SOURCE: {source}", f"ARCHIVE: {destination}", f"REASON: {reason}", f"SIZE: {size} bytes", ""]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def choose_action() -> str:
    print("\nChoose an action:")
    print("  1. Create a preview report only (recommended first)")
    print("  2. Move the listed candidates into one root backup folder")
    print("  Q. Quit")
    while True:
        choice = input("Choice: ").strip().casefold()
        if choice in {"1", "preview", "p"}:
            return "preview"
        if choice in {"2", "move", "m"}:
            return "move"
        if choice in {"q", "quit", "exit"}:
            raise SystemExit(0)
        print("Please enter 1, 2, or Q.")


def main() -> None:
    print(f"Website folder: {ROOT}")
    if not ROOT.is_dir():
        raise FileNotFoundError(f"The website folder does not exist: {ROOT}")

    slideshow_refs = files_referenced_by_run_images()
    html_refs = text_references()
    candidates = candidate_files(slideshow_refs, html_refs)
    total_size = sum(path.stat().st_size for path, _ in candidates)

    print(f"Active slideshow media protected: {len(slideshow_refs)} file reference(s)")
    print(f"Direct current HTML/text references protected: {len(html_refs)} file reference(s)")
    print(f"Clearly archival candidates found: {len(candidates)} file(s), {format_size(total_size)}")
    if not candidates:
        print("Nothing matched the safe archival rules. No files were changed.")
        return

    print("\nFirst 30 candidates:")
    for path, reason in candidates[:30]:
        print(f"  {rel(path)} — {reason}")
    if len(candidates) > 30:
        print(f"  ... plus {len(candidates) - 30} more. See the preview log for the full list.")

    action = choose_action()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_folder = ROOT / f"{ARCHIVE_PREFIX}{stamp}"
    archive_folder.mkdir(parents=True, exist_ok=False)

    if action == "preview":
        report = write_report(archive_folder, candidates)
        print("\nPreview complete. No files were moved.")
        print(f"Report: {report}")
        return

    confirmation = input("Type MOVE to archive exactly these candidates, or press Enter to cancel: ").strip()
    if confirmation != "MOVE":
        report = write_report(archive_folder, candidates)
        print("Cancelled. No files were moved.")
        print(f"Preview report: {report}")
        return

    moved: list[tuple[str, str, str, int]] = []
    for source, reason in candidates:
        # Files can change between scan and move; skip safely if no longer present.
        if not source.exists():
            continue
        original = source.resolve()
        destination = archive_folder / original.relative_to(ROOT.resolve())
        destination.parent.mkdir(parents=True, exist_ok=True)
        size = original.stat().st_size
        shutil.move(str(original), str(destination))
        moved.append((str(original), str(destination), reason, size))

    report = write_report(archive_folder, candidates, moved)
    print(f"\nArchived {len(moved)} file(s) into: {archive_folder}")
    print(f"Log: {report}")
    print("No files were deleted. To restore a file, move it back to the SOURCE location recorded in log.txt.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. No files were moved.")
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
