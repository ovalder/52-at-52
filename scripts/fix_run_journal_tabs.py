#!/usr/bin/env python3
"""Fix 52@52 navigation: keep only Run Journal, Data, Tips & Reviews, and Summary.

Save beside index.html and run:
  python3 fix_run_journal_tabs.py

A timestamped backup of index.html is created first.
"""
from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

root = Path(__file__).resolve().parent
index = root / "index.html"
if not index.exists():
    sys.exit("ERROR: index.html was not found beside this script.")

source = index.read_text(encoding="utf-8")
if '<nav class="tab-nav">' not in source or '</nav>' not in source:
    sys.exit("ERROR: Could not find the expected tab navigation. No changes were made.")

backup = root / f"index.before-tab-fix-{datetime.now():%Y%m%d-%H%M%S}.html"
shutil.copy2(index, backup)

new_nav = '''<nav class="tab-nav">
    <button class="tab-btn active" onclick="switchTab('all-runs', event)">🏃 <span class="txt" data-en="Run Journal" data-pt="Diário das Corridas">Run Journal</span></button>
    <button class="tab-btn" onclick="switchTab('data', event)">📊 <span class="txt" data-en="Data" data-pt="Dados & Gráficos">Data</span></button>
    <button class="tab-btn" onclick="switchTab('tips', event)">💡 <span class="txt" data-en="Tips & Reviews" data-pt="Dicas & Reviews">Tips & Reviews</span></button>
    <button class="tab-btn" onclick="switchTab('summary', event)">📖 <span class="txt" data-en="Summary" data-pt="Resumos">Summary</span></button>
  </nav>'''

source, nav_replacements = re.subn(r'<nav class="tab-nav">.*?</nav>', new_nav, source, count=1, flags=re.DOTALL)
if nav_replacements != 1:
    shutil.copy2(backup, index)
    sys.exit("ERROR: Could not replace the navigation. The original was restored.")

source = re.sub(
    r'\s*<!--\s*TAB\s*1:\s*LAST RUN\s*-->\s*<div id="pane-last-run" class="tab-pane(?:\s+active)?">.*?</div>\s*(?=<!--\s*TAB|<div id="pane-all-runs")',
    '\n',
    source,
    count=1,
    flags=re.DOTALL | re.IGNORECASE,
)
source = source.replace('<div id="pane-all-runs" class="tab-pane">', '<div id="pane-all-runs" class="tab-pane active">', 1)
source = source.replace('<div id="pane-all-runs" class="tab-pane active active">', '<div id="pane-all-runs" class="tab-pane active">')
source = source.replace("if (tabId === 'last-run') renderLastRun();\n    else if (tabId === 'all-runs') applyAllRunsFilter();", "if (tabId === 'all-runs') applyAllRunsFilter();")
source = source.replace("if (tabId === 'last-run') renderLastRun();\r\n    else if (tabId === 'all-runs') applyAllRunsFilter();", "if (tabId === 'all-runs') applyAllRunsFilter();")
source = source.replace("      renderLastRun();\n      renderSelectedRun();", "      renderSelectedRun();")
source = source.replace("      renderLastRun();\r\n      renderSelectedRun();", "      renderSelectedRun();")
source = source.replace("    renderLastRun();\n    applyAllRunsFilter();", "    applyAllRunsFilter();")
source = source.replace("    renderLastRun();\r\n    applyAllRunsFilter();", "    applyAllRunsFilter();")

index.write_text(source, encoding="utf-8")
print("Done.")
print("Updated: " + str(index))
print("Backup:  " + str(backup))
print("Expected tabs: Run Journal | Data | Tips & Reviews | Summary")
