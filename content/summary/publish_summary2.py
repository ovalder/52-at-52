#!/usr/bin/env python3
# Publish COMPLETED summary. Dependencies: Pillow Markdown. No automatic deployment.
import html
import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
ROOT=Path(r"C:\Users\valde\OneDrive\Documents\52-at-52")
SOURCE=ROOT/"content/summary"
SLUG="challenge-summary"
RUNTIME='<script id="completed-slideshow-runtime">\n(()=>{\nlet timer=null, current=null, index=0;\nfunction schedule(delay){clearTimeout(timer);if(!current||current.querySelectorAll(\'img\').length<2)return;timer=setTimeout(()=>{if(!current.isConnected){clearTimeout(timer);return;}show(index+1);schedule(3000);},delay);}\nfunction show(n){const imgs=current.querySelectorAll(\'img\');index=(n+imgs.length)%imgs.length;imgs.forEach((im,i)=>im.hidden=i!==index);current.querySelector(\'[data-counter]\').textContent=`${index+1} / ${imgs.length}`;}\nfunction init(){const gallery=document.querySelector(\'#summaryInlineContent [data-completed-slideshow]\');if(gallery===current)return;clearTimeout(timer);current=gallery;index=0;if(!gallery)return;show(0);gallery.onclick=e=>{const b=e.target.closest(\'[data-step]\');if(b)show(index+Number(b.dataset.step));schedule(10000);};gallery.onkeydown=e=>{if(e.key===\'ArrowRight\'||e.key===\'ArrowLeft\'){e.preventDefault();show(index+(e.key===\'ArrowRight\'?1:-1));schedule(10000);}};schedule(3000);}\nfunction start(){const box=document.getElementById(\'summaryInlineContent\');if(box)new MutationObserver(init).observe(box,{childList:true});init();}\nif(document.readyState===\'loading\')document.addEventListener(\'DOMContentLoaded\',start);else start();\n})();\n</script>'

def photo_key(p):
    name=p.stem.casefold()
    m=re.search(r'(?:run|race|corrida)[ _#-]*0*(\d{1,2})(?!\d)',name)
    if not m:
        m=re.search(r'(?<!\d)0*(\d{1,2})(?!\d)',name)
    n=int(m.group(1)) if m else 999
    parts=tuple((0,int(s)) if s.isdigit() else (1,s) for s in re.split(r'(\d+)',name))
    return n,parts

def language(p):
    s=p.stem.casefold()
    if re.search(r'(?:^|[-_ ])pt(?:$|[-_ ])|portugu[eê]s|portuguese|corrida',s):return 'pt'
    if re.search(r'(?:^|[-_ ])en(?:$|[-_ ])|english|ingl[eê]s',s):return 'en'
    return None

def patch_index(text,card):
    begin='<!-- summary-publisher:challenge-summary:start -->'
    end='<!-- summary-publisher:challenge-summary:end -->'
    if begin in text or end in text:
        if text.count(begin)!=1 or text.count(end)!=1:raise ValueError('Ambiguous summary markers')
        a,b=text.index(begin),text.index(end)
        if b<a:raise ValueError('Invalid summary markers')
        text=text[:a]+text[b+len(end):]
    pane=re.search(r'<div\b[^>]*id=[\'"]pane-summary[\'"][^>]*>',text)
    article=re.search(r'<article\b[^>]*id=[\'"]summaryInlineContent[\'"]',text)
    if not pane or not article:raise ValueError('Expected Summary tab not found; nothing changed')
    grid=re.search(r'<div\b[^>]*class=[\'"]card-grid[\'"][^>]*>',text[pane.end():article.start()])
    if not grid:raise ValueError('Summary card grid not found')
    a=pane.end()+grid.end()
    b=article.start()
    section=text[a:b]
    section=re.sub(r'class="info-card active"','class="info-card"',section)
    text=text[:a]+'\n'+begin+'\n'+card+'\n'+end+'\n'+section+text[b:]
    # Opening this tab should always choose COMPLETED, even after reading another summary.
    old="const c=document.querySelector('#pane-summary .info-card.active')||document.querySelector('#pane-summary .info-card');"
    new="const c=document.querySelector('#completed-summary-card')||document.querySelector('#pane-summary .info-card.active')||document.querySelector('#pane-summary .info-card');"
    if old not in text and new not in text:raise ValueError('Summary tab selection code differs; no files changed')
    text=text.replace(old,new)
    text=re.sub(r'<script id="completed-slideshow-runtime">.*?</script>\s*','',text,flags=re.S)
    if '</body>' not in text:raise ValueError('Missing closing body tag')
    return text.replace('</body>',RUNTIME+'\n</body>',1)

def main():
    try:
        import markdown
        from PIL import Image,ImageOps
    except ImportError:raise RuntimeError('Install dependencies: py -m pip install Pillow Markdown')
    index=ROOT/'index.html'
    raw=index.read_bytes()
    stories={}
    files=sorted(p for p in SOURCE.iterdir() if p.suffix.lower() in {'.md','.markdown'})
    if len(files)!=2:raise ValueError('Expected exactly two Markdown files, one -en.md and one -pt.md')
    for p in files:
        lang=language(p)
        if not lang or lang in stories:raise ValueError('Use distinct -en.md and -pt.md filenames')
        stories[lang]=p.read_text(encoding='utf-8-sig')
    if set(stories)!={'en','pt'}:raise ValueError('Both languages required')
    photos=sorted((p for p in SOURCE.iterdir() if p.is_file() and p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}),key=photo_key)
    titles={}
    for lang,text in stories.items():
        m=re.search(r'(?m)^#\s+(.+)',text)
        titles[lang]=re.sub(r'[*_`]','',m.group(1)).strip() if m else ('Challenge completed' if lang=='en' else 'Desafio concluído')
    esc=lambda s:html.escape(s,quote=True)
    card=(f'<div id="completed-summary-card" class="info-card active" onclick="loadInlineSummary(\'{SLUG}\',this)">'
          '<div><span class="info-badge" style="background:rgba(168,85,247,.15);color:#a855f7;">COMPLETED</span>'
          f'<div class="info-title txt" data-en="{esc(titles["en"])}" data-pt="{esc(titles["pt"])}">{esc(titles["en"])}</div>'
          '<p class="info-desc txt" data-en="The complete challenge: photos and reflections." data-pt="O desafio completo: fotos e reflexões.">The complete challenge: photos and reflections.</p></div></div>')
    patched=patch_index(raw.decode('utf-8-sig'),card)
    print('Photo order:')
    for p in photos:print(f'  Run {photo_key(p)[0] if photo_key(p)[0]!=999 else "unknown"}: {p.name}')
    print('Unnumbered photos appear last. Autoplay: 3 seconds. Click: hold current slide for 10 seconds.')
    print('COMPLETED becomes the first/default summary. Existing summaries and Data tab are preserved.')
    if input('Type PUBLISH to continue (Enter cancels): ').strip()!='PUBLISH':return
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    media_rel=f'media/{SLUG}/{stamp}'
    outputs={}; images=[]; mapping={}
    with tempfile.TemporaryDirectory() as temp:
        for i,p in enumerate(photos,1):
            name=f'photo-{i:03d}.webp'; out=Path(temp)/name
            with Image.open(p) as opened:
                im=ImageOps.exif_transpose(opened);im.thumbnail((2000,2000),Image.Resampling.LANCZOS)
                im=im.convert('RGBA' if 'A' in im.getbands() else 'RGB');im.save(out,'WEBP',quality=84,method=6)
            url=f'{media_rel}/{name}';mapping[p.name]=url;outputs[ROOT/url]=out.read_bytes()
            images.append(f'<img src="{url}" alt="{esc(p.stem)}" {"hidden" if i>1 else ""} style="width:100%;height:min(65vh,600px);object-fit:contain;" >')
        gallery=('''<section data-completed-slideshow tabindex="0" aria-label="Summary slideshow" style="background:#0f172a;border-radius:12px;overflow:hidden;margin-bottom:24px;">
<div>'''+''.join(images)+'''</div><div style="display:flex;justify-content:space-between;align-items:center;padding:10px;">
<button type="button" data-step="-1" aria-label="Previous photo">&#10094;</button><span data-counter style="color:white;"></span><button type="button" data-step="1" aria-label="Next photo">&#10095;</button>
</div></section>''') if images else ''
        for lang,text in stories.items():
            body=markdown.markdown(text,extensions=['extra','sane_lists'])
            from urllib.parse import unquote
            def rewrite(m):
                value=unquote(html.unescape(m.group(2)));key=value[2:] if value.startswith('./') else value
                return f'src={m.group(1)}{mapping[key]}{m.group(1)}' if key in mapping else m.group(0)
            body=re.sub(r'src=([\'"])(.*?)\1',rewrite,body)
            outputs[ROOT/'summaries'/f'{SLUG}-{lang}.html']=(gallery+'\n'+body+'\n').encode('utf-8')
        outputs[index]=patched.encode('utf-8')
        if index.read_bytes()!=raw:raise RuntimeError('index.html changed; rerun')
        backup=ROOT/'backups'/f'summary-{stamp}'
        for p in outputs:
            if p.exists():
                dest=backup/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        for p,data in outputs.items():
            p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.summary.tmp');tmp.write_bytes(data);tmp.replace(p)
            print('Written:',p.relative_to(ROOT))
    print('Done. Commit/push index.html, summaries/, and new media/challenge-summary/ assets.')
    print('Source files unchanged; no automatic deployment. Backups:',backup)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',exc)
        raise SystemExit(1)
