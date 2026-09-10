# 52@52 publishing workflow

This workflow preserves the existing single-page website:

- **Last Run** automatically displays the highest run number.
- **All Runs** uses the existing filters, selector, slideshow, and Previous/Next controls.
- **Data** uses `posts.json` for charts and filtered totals.
- **Tips & Reviews** and **Summary** are unchanged.
- The EN/PT control at the top applies to the full site and loads the matching post file.

## One-time setup

From the website root folder, install the image library:

```bash
python3 -m pip install -r scripts/requirements.txt
```

## Folder layout

Create this folder in the website root:

```text
incoming-runs/
```

For each completed run, create a folder inside it:

```text
incoming-runs/run-44/
├── metadata.txt
├── run-en.md
├── run-pt.md
└── images/
    ├── 001.jpg
    ├── 002.jpg
    └── route-map.png
```

Copy the template files from `content/new-runs/_template/` when starting a new run.

## metadata.txt

Required fields:

```text
run: 44
date: 2026-09-06
location: City, State/Province, Country
distance_miles: 13.10
duration: 02:10:00
shoes: Shoe model
```

Optional fields include `distance_km`, `region`, `device`, `elevation_ft`, `audiobook`, `company`, `summary_en`, and `summary_pt`.

Use a vertical bar between company names:

```text
company: Paula Loures | Mark Lee | Jeff Bowers
```

Leave `elevation_ft` blank when it is not known. The script writes `null` rather than guessing zero.

## Markdown and YouTube videos

Write the English and Portuguese articles in `run-en.md` and `run-pt.md`.

Use normal Markdown headings, paragraphs, lists, bold text, italics, and links. Put a YouTube URL on a line by itself to embed it exactly at that point in the article:

```markdown
This is the paragraph above the video.

https://www.youtube.com/watch?v=VIDEO_ID

This is the paragraph below the video.
```

Supported forms include `youtube.com/watch?v=...`, `youtu.be/...`, and `youtube.com/embed/...`.

## Publish a run locally

From the website root, run:

```bash
python3 scripts/publish_run.py
```

When prompted, enter the folder name, for example:

```text
run-44
```

The script will:

1. Create/update `posts/run-44-en.html` and `posts/run-44-pt.html`.
2. Turn standalone YouTube URLs in Markdown into responsive embedded players.
3. Correct phone-image orientation from EXIF data.
4. Resize every image to a maximum of **2,000 pixels on the longest edge**.
5. Convert photos to optimized WebP and preserve maps/transparency as optimized PNG.
6. Copy optimized images into `media/` using names such as `run44_001.webp`.
7. Update `posts.json` for filters, metric cards, and Data charts.
8. Update `run_images.json` for the slideshow.
9. Calculate pace from duration and miles.

The originals remain in `incoming-runs/run-44/images/`; only optimized copies are placed in `media/`.

## Test before deployment

From the website root:

```bash
python3 -m http.server 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

Test:

- Last Run shows the new run.
- All Runs selects and filters the new run.
- Both EN and PT show their correct article.
- Slideshow images appear and advance.
- YouTube embeds work.
- Data totals and charts include the new run.
- Tips & Reviews and Summary still load.

Stop the local server with `Control + C` in Terminal.

## Run 43 migration

The generated `posts/run-43-en.html`, `posts/run-43-pt.html`, `posts.json`, and `run_images.json` supplied with this package correct the Run 43 content and metadata.

Before using the supplied Run 43 `run_images.json`, use the publisher once with the actual Run 43 source folder and its images. It will create the real optimized WebP files in `media/` and write the exact slideshow file list automatically.
