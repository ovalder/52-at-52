#!/usr/bin/env python3
"""Build a bilingual summary and photo gallery, and register its Summary-tab card.
Requires: py -m pip install Pillow Markdown
Does not deploy or change any run data.
"""
import html
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
SOURCE = ROOT / "content" / "summary"
SLUG = "challenge-summary"
IMAGES = {".jpg", ".jpeg", ".png", ".webp"}

def identify_language(path):
    name = path.stem.casefold()
    if re.search(r"(?:^|[-_ ])pt(?:$|[-_ ])|portugu[eê]s|portuguese|corrida", name):
        return "pt"
    if re.search(r"(?:^|[-_ ])en(?:$|[-_ ])|english|ingl[eê]s", name):
        return "en"
    return None

def heading(text, default):
    match = re.search(r"(?m)^#\s+(.+?)\s*#*\s*$", text)
    value = match.group(1) if match else default
    return re.sub(r"[*_`]", "", value).strip()

def update_index(content, card):
    start = "<!-- summary-publisher:challenge-summary:start -->"
    end = "<!-- summary-publisher:challenge-summary:end -->"
    block = start + "\n" + card + "\n" + end
    if start in content or end in content:
        if content.count(start) != 1 or content.count(end) != 1:
            raise ValueError("Ambiguous publisher markers in index.html")
        a, b = content.index(start), content.index(end)
        if b < a:
            raise ValueError("Invalid publisher marker order")
        return content[:a] + block + content[b + len(end):]
    pane = re.search(r'id\s*=\s*[\'"]pane-summary[\'"]', content)
    article = re.search(r'<article\b[^>]*id\s*=\s*[\'"]summaryInlineContent[\'"]', content)
    if not pane or not article or article.start() < pane.start():
        raise ValueError("Cannot find the existing Summary tab; index.html was not changed")
    close_grid = content.rfind("</div>", pane.end(), article.start())
    if close_grid < 0:
        raise ValueError("Cannot locate Summary card grid closing tag")
    if "loadInlineSummary" not in content:
        raise ValueError("Expected Summary loader is missing")
    return content[:close_grid] + "\n" + block + "\n" + content[close_grid:]

def main():
    try:
        import markdown
        from PIL import Image, ImageOps
    except ImportError:
        raise RuntimeError("Install dependencies: py -m pip install Pillow Markdown")
    index = ROOT / "index.html"
    if not SOURCE.is_dir() or not index.is_file():
        raise FileNotFoundError(f"Required source folder or index.html missing. Source: {SOURCE}")
    md = sorted(p for p in SOURCE.iterdir() if p.is_file() and p.suffix.lower() in {".md", ".markdown"})
    if len(md) != 2:
        raise ValueError(f"Expected exactly two Markdown files in {SOURCE}; found {len(md)}")
    stories = {}
    for p in md:
        language = identify_language(p)
        if not language or language in stories:
            raise ValueError("Use filenames ending in -en.md and -pt.md to identify the two languages")
        stories[language] = p.read_text(encoding="utf-8-sig")
    if set(stories) != {"en", "pt"}:
        raise ValueError("Both English and Portuguese stories are required")
    photos = sorted((p for p in SOURCE.iterdir() if p.is_file() and p.suffix.lower() in IMAGES),
                    key=lambda p: ("gemini" not in p.name.casefold(), p.name.casefold()))
    titles = {lang: heading(text, "Challenge Summary" if lang == "en" else "Resumo do Desafio")
              for lang, text in stories.items()}
    esc = lambda s: html.escape(s, quote=True)
    card = (f'<div class="info-card" onclick="loadInlineSummary(\'{SLUG}\',this)">'
            f'<div><span class="info-badge">52@52</span>'
            f'<div class="info-title txt" data-en="{esc(titles["en"])}" '
            f'data-pt="{esc(titles["pt"])}">{esc(titles["en"])}</div>'
            '<p class="info-desc txt" data-en="Photos and reflections from the challenge." '
            'data-pt="Fotos e reflexões do desafio.">Photos and reflections from the challenge.</p>'
            '</div></div>')
    original = index.read_bytes()
    patched = update_index(original.decode("utf-8-sig"), card)
    print(f"Source: {SOURCE}\nEnglish: {titles['en']}\nPortuguese: {titles['pt']}")
    print(f"Photos: {len(photos)} (Gemini images first, then filename order)")
    if not photos:
        print("No photos yet: text-only publication is supported. Rerun after adding photos.")
    print("Creates/updates summaries/challenge-summary-en.html and -pt.html, a dedicated media folder,")
    print("and one Summary-tab card. Existing summary cards and all run data are preserved.")
    if input("Type PUBLISH to continue (Enter cancels): ").strip() != "PUBLISH":
        print("Cancelled. No files changed.")
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    media_rel = f"media/{SLUG}/{stamp}"
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        outputs = {}
        gallery = []
        for i, photo in enumerate(photos, 1):
            name = f"photo-{i:03d}.webp"
            staged = stage / name
            with Image.open(photo) as opened:
                im = ImageOps.exif_transpose(opened)
                im.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
                im.save(staged, "WEBP", quality=84, method=6)
            url = f"{media_rel}/{name}"
            outputs[ROOT / url] = staged.read_bytes()
            gallery.append(f'<a href="{url}" target="_blank" rel="noopener" style="flex:0 0 90%;scroll-snap-align:start;">'
                           f'<img src="{url}" alt="Summary photo {i}" loading="lazy" '
                           'style="width:100%;max-height:600px;object-fit:contain;border-radius:12px;"></a>')
        strip = ('<div style="display:flex;overflow-x:auto;gap:12px;scroll-snap-type:x mandatory;">'
                 + "".join(gallery) + '</div>') if gallery else ""
        for language, text in stories.items():
            body = markdown.markdown(text, extensions=["extra", "sane_lists"])
            # Locally referenced photos in Markdown use the processed, published versions too.
            for i, photo in enumerate(photos, 1):
                url = f"{media_rel}/photo-{i:03d}.webp"
                from urllib.parse import unquote
                def rewrite(m):
                    value = unquote(html.unescape(m.group(2)))
                    return f'src={m.group(1)}{url}{m.group(1)}' if value in {photo.name, "./"+photo.name} else m.group(0)
                body = re.sub(r'src=([\'"])(.*?)\1', rewrite, body)
            outputs[ROOT / "summaries" / f"{SLUG}-{language}.html"] = (strip + "\n" + body + "\n").encode("utf-8")
        outputs[index] = patched.encode("utf-8")
        if index.read_bytes() != original:
            raise RuntimeError("index.html changed during preparation. Please rerun.")
        backup = ROOT / "backups" / f"summary-{stamp}"
        for target in outputs:
            if target.exists():
                dest = backup / target.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, dest)
        # Publish new assets first and index last; never delete existing gallery assets.
        for target, data in outputs.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".summary.tmp")
            temporary.write_bytes(data)
            temporary.replace(target)
            print(f"Written: {target.relative_to(ROOT)}")
    print("Done. Commit/push index.html, summaries/, and the new media/challenge-summary/ assets.")
    print("Nothing was deployed automatically. Originals were not modified. Backups:", backup)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
