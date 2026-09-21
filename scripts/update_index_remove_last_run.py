#!/usr/bin/env python3
"""Update an existing 52@52 index.html to remove Last Run and make Run Journal the default tab.

Save this file in the website root, next to index.html, then run:
  python3 update_index_remove_last_run.py

It creates index.before-run-journal.html as a backup, then updates index.html.
"""
from pathlib import Path
import re
import shutil
import sys

root = Path(__file__).resolve().parent
index = root / "index.html"
backup = root / "index.before-run-journal.html"

if not index.exists():
    sys.exit("ERROR: index.html was not found beside this script.")

source = index.read_text(encoding="utf-8")
if "pane-last-run" not in source:
    sys.exit("ERROR: This index.html does not contain the expected Last Run pane. No changes were made.")

if not backup.exists():
    shutil.copy2(index, backup)

source, nav_count = re.subn(
    r'\s*<button class="tab-btn active" onclick="switchTab\(\'last-run\', event\)">.*?</button>\s*'
    r'<button class="tab-btn" onclick="switchTab\(\'all-runs\', event\)">',
    '''\n    <button class="tab-btn active" onclick="switchTab('all-runs', event)">\n      🏃 <span class="txt" data-en="Run Journal" data-pt="Diário das Corridas">Run Journal</span>\n    </button>\n    <button class="tab-btn" onclick="switchTab('data', event)">''',
    source,
    count=1,
    flags=re.DOTALL,
)

if nav_count != 1:
    index.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
    sys.exit("ERROR: Could not safely update the tab navigation. Restored the backup; no changes were kept.")

source, pane_count = re.subn(
    r'\s*<!-- TAB 1: LAST RUN -->\s*<div id="pane-last-run" class="tab-pane active">\s*<div id="lastRunContainer"></div>\s*</div>\s*',
    '\n\n  <!-- TAB 1: RUN JOURNAL -->\n',
    source,
    count=1,
    flags=re.DOTALL,
)
source = source.replace('<!-- TAB 2: ALL RUNS -->\n  <div id="pane-all-runs" class="tab-pane">', '<div id="pane-all-runs" class="tab-pane active">')
source = source.replace("if (tabId === 'last-run') renderLastRun();\n    else if (tabId === 'all-runs') applyAllRunsFilter();", "if (tabId === 'all-runs') applyAllRunsFilter();")
source = source.replace("      renderLastRun();\n      renderSelectedRun();", "      renderSelectedRun();")
source = source.replace("    renderLastRun();\n    applyAllRunsFilter();", "    applyAllRunsFilter();")

video_css = '''\n    .video-embed {\n      position: relative;\n      width: 100%;\n      aspect-ratio: 16 / 9;\n      margin: 24px 0;\n      overflow: hidden;\n      border-radius: var(--radius-md);\n      border: 1px solid var(--card-border);\n      background: #030508;\n    }\n    .video-embed iframe {\n      position: absolute;\n      inset: 0;\n      width: 100%;\n      height: 100%;\n      border: 0;\n    }\n'''
if ".video-embed" not in source:
    marker = "    .run-body img, .article-body img { max-width: 100%; border-radius: 12px; border: 1px solid var(--card-border); margin: 16px 0; }"
    if marker in source:
        source = source.replace(marker, marker + video_css)
    else:
        source = source.replace("  </style>", video_css + "  </style>", 1)

index.write_text(source, encoding="utf-8")
print("Done.")
print("Updated: index.html")
print("Backup:  index.before-run-journal.html")
print("Run Journal is now the default tab; Last Run is removed.")
