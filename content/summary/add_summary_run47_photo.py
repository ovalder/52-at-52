#!/usr/bin/env python3
"""Add Grun47.jpg to both published COMPLETED galleries without changing index.html."""
import hashlib
import html
import io
import re
import shutil
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
SOURCE = ROOT / "content/summary/Grun47.jpg"

class ImageInfo(HTMLParser):
    def __init__(self, tag):
        super().__init__()
        self.attrs = {}
        self.feed(tag)
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'img': self.attrs = dict(attrs)

def run_key(tag):
    attrs = ImageInfo(tag).attrs
    name = attrs.get('alt', '')
    match = re.search(r'(?:run|race|corrida)[ _#-]*0*(\d{1,2})(?!\d)', name, re.I)
    if not match:
        match = re.search(r'(?<!\d)0*(\d{1,2})(?!\d)', name)
    return int(match.group(1)) if match else 999

def patch(text, url):
    pattern = r'<section\b(?=[^>]*\bdata-completed-slideshow\b)[^>]*>.*?</section>'
    matches = list(re.finditer(pattern, text, flags=re.S | re.I))
    if len(matches) != 1:
        raise ValueError('Expected exactly one COMPLETED slideshow; nothing changed')
    match = matches[0]
    gallery = match.group(0)
    tags = re.findall(r'<img\b[^>]*>', gallery, flags=re.I)
    if not tags:
        raise ValueError('No existing slideshow images; cannot safely insert')
    retained = []
    for tag in tags:
        attrs = ImageInfo(tag).attrs
        if attrs.get('alt', '').casefold() == 'grun47' or '/grun47-' in attrs.get('src', '').casefold():
            continue
        retained.append(tag)
    retained.append(f'<img src="{html.escape(url, quote=True)}" alt="Grun47" hidden style="width:100%;height:min(65vh,600px);object-fit:contain;">')
    retained.sort(key=run_key)
    normalized = []
    for i, tag in enumerate(retained):
        tag = re.sub(r'\s+hidden(?:\s*=\s*(?:"[^"]*"|\x27[^\x27]*\x27|[^\s>]+))?', '', tag, flags=re.I)
        if i:
            tag = re.sub(r'<img\b', '<img hidden', tag, count=1, flags=re.I)
        normalized.append(tag)
    # Preserve the carousel wrapper and controls; replace only its image elements.
    first = True
    def replace(m):
        nonlocal first
        if first:
            first = False
            return ''.join(normalized)
        return ''
    gallery = re.sub(r'<img\b[^>]*>', replace, gallery, flags=re.I)
    return text[:match.start()] + gallery + text[match.end():], len(normalized)

def main():
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise RuntimeError('Install Pillow first: py -m pip install Pillow')
    if not SOURCE.is_file():
        raise FileNotFoundError(f'Photo not found: {SOURCE}')
    with Image.open(SOURCE) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
        im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
        buffer = io.BytesIO()
        im.save(buffer, 'WEBP', quality=84, method=6)
    image_bytes = buffer.getvalue()
    digest = hashlib.sha256(image_bytes).hexdigest()[:12]
    url = f'media/challenge-summary/additions/grun47-{digest}.webp'
    plans = []
    for lang in ('en','pt'):
        p = ROOT / 'summaries' / f'challenge-summary-{lang}.html'
        original = p.read_bytes()
        revised, count = patch(original.decode('utf-8-sig'), url)
        plans.append((p, original, revised.encode('utf-8')))
        print(f'{p.name}: {count} slides after adding Grun47 (ordered by run number)')
    print('index.html, initial Summary tab, slideshow timing, story text and run statistics will not change.')
    if input('Type FIX to publish locally (Enter cancels): ').strip() != 'FIX':
        print('Cancelled. No files changed.')
        return
    for p, original, _ in plans:
        if p.read_bytes() != original:
            raise RuntimeError(f'File changed during preview: {p}; rerun')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = ROOT / 'backups' / f'summary-run47-{stamp}'
    for p, _, _ in plans:
        dest = backup / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    target = ROOT / url
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    for p, _, revised in plans:
        temp = p.with_name(p.name + '.run47.tmp')
        temp.write_bytes(revised)
        temp.replace(p)
        assert p.read_bytes() == revised
    print('Done. Commit/push both summary HTML files and this image:', url)
    print('Backups:', backup)
    print('No files were deployed automatically; the original JPEG was not modified.')

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('ERROR:', exc)
        raise SystemExit(1)
