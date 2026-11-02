#!/usr/bin/env python3
"""Correct JSON elevations and original per-run data.txt files; no deployment."""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
FIXES = {31: 121, 32: 110, 33: 181}

def records(document):
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in ("runs", "posts", "items", "data"):
            if isinstance(document.get(key), list):
                return document[key]
    raise ValueError("Cannot identify JSON run records")

def run_number(record):
    for key in ("race", "run_number", "run"):
        try:
            return int(record.get(key))
        except (ValueError, TypeError):
            pass
    return None

def patch_metadata(text, run):
    pattern = r"(?im)^[ \t]*elevation_ft[ \t]*:[^\r\n]*"
    matches = list(re.finditer(pattern, text))
    if len(matches) > 1:
        raise ValueError("Duplicate elevation_ft fields")
    line = f"elevation_ft: {FIXES[run]}"
    if matches:
        m = matches[0]
        return text[:m.start()] + line + text[m.end():]
    newline = "\r\n" if "\r\n" in text else "\n"
    return text + (newline if text and not text.endswith(("\n", "\r")) else "") + line + newline

def main():
    if not ROOT.is_dir():
        raise FileNotFoundError(ROOT)
    plans = []
    public = ROOT / "posts.json"
    if not public.is_file():
        raise FileNotFoundError(public)
    for path in (public, ROOT / "data/runs.json", ROOT / "data/runs-2.json"):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8-sig"))
        seen = set()
        changes = []
        for record in records(document):
            if not isinstance(record, dict):
                continue
            run = run_number(record)
            if run not in FIXES:
                continue
            if run in seen:
                raise ValueError(f"Duplicate Run {run}: {path}")
            seen.add(run)
            old = record.get("elevation_ft", "missing")
            if old != FIXES[run]:
                record["elevation_ft"] = FIXES[run]
                changes.append(f"Run {run}: {old} -> {FIXES[run]} ft")
        if path == public and seen != set(FIXES):
            raise ValueError(f"Missing target runs in posts.json: {sorted(set(FIXES)-seen)}")
        if changes:
            new = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            plans.append((path, raw, new, "; ".join(changes)))
    found = set()
    source = ROOT / "content/new-runs"
    if source.is_dir():
        for path in sorted(source.rglob("data.txt")):
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            declared = re.findall(r"(?im)^\s*(?:run|race|run_number)\s*:\s*(\d+)\s*$", text)
            folder = re.fullmatch(r"run[ _-]*0*(\d+)", path.parent.name, re.I)
            folder_run = int(folder.group(1)) if folder else None
            numbers = {int(n) for n in declared}
            if not (numbers & set(FIXES)) and folder_run not in FIXES:
                continue
            if len(numbers) > 1:
                raise ValueError(f"Conflicting run identifiers: {path}")
            declared_run = next(iter(numbers), None)
            if folder_run is not None and declared_run is not None and folder_run != declared_run:
                raise ValueError(f"Folder/data.txt run mismatch: {path}; fix run number first")
            run = declared_run if declared_run is not None else folder_run
            if run not in FIXES:
                continue
            found.add(run)
            patched = patch_metadata(text, run)
            if patched != text:
                bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
                plans.append((path, raw, bom + patched.encode("utf-8"), f"Run {run}: elevation_ft -> {FIXES[run]}"))
    missing = sorted(set(FIXES) - found)
    if missing:
        print(f"WARNING: Original data.txt files not found for runs {missing} under {source}")
        print("Those originals will NOT be fixed. JSON corrections can still proceed.")
    if not plans:
        print("No changes needed in discovered files.")
        return
    for path, _, _, description in plans:
        print(f"{path.relative_to(ROOT)}: {description}")
    if input("Type FIX to back up and update these files (Enter cancels): ").strip() != "FIX":
        print("Cancelled. No changes made.")
        return
    # Refuse writes if a file has changed since the preview.
    for path, raw, _, _ in plans:
        if path.read_bytes() != raw:
            raise RuntimeError(f"File changed during preview: {path}. Run again.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for path, _, _, _ in plans:
        shutil.copy2(path, path.with_name(f"{path.stem}.backup-elevation-{stamp}{path.suffix}"))
    for path, _, new, _ in plans:
        temp = path.with_name(path.name + ".elevation-fix.tmp")
        temp.write_bytes(new)
        temp.replace(path)
        if path.read_bytes() != new:
            raise RuntimeError(f"Verification failed: {path}")
        print(f"Updated and verified: {path.relative_to(ROOT)}")
    print("Done. Commit/push the website JSON changes to deploy. No Git operations were performed.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
