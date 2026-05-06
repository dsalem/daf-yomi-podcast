# daf-yomi-podcast

Bulk-publish a back-catalog of daf-yomi shiurim to **Internet Archive** (free,
permanent audio hosting) and generate a **podcast RSS feed** that Spotify,
Apple Podcasts, Overcast, and every other podcast app can ingest.

Built for the "Daf Yomi" show by Rabbi Joseph Salem: 2,300 m4a recordings
from Masechet Berachot through Chullin, sitting in Google Drive, that need to
become a real podcast.

## What it does

1. **scan** — walks a local mirror of your Drive folder, parses filenames like
   `Berachot 47.m4a`, builds a manifest in SQLite.
2. **normalize** — runs ffmpeg `loudnorm` on each shiur (target -16 LUFS,
   Spotify's recommended level), outputs 64 kbps mono mp3.
3. **upload** — pushes the normalized files to Internet Archive via the
   `internetarchive` Python package. Stable identifiers like
   `rabbi-joseph-salem-daf-yomi-berachot-047`.
4. **rss** — emits a single `feed.xml` with full iTunes / Spotify metadata
   (cover art, seasons, episodes, Hebrew subtitles, durations, pub dates).
5. **status** — shows progress by masechet.

Everything is idempotent and incremental; re-running picks up only new work.

## One-time setup

### 1. Install Python 3.11+ and ffmpeg

- Windows: `winget install ffmpeg` (or download from https://ffmpeg.org)
- macOS: `brew install ffmpeg`
- Linux: `apt install ffmpeg` / `dnf install ffmpeg`

Verify: `ffmpeg -version` and `ffprobe -version`.

### 2. Create an Internet Archive account

Go to https://archive.org/account/signup and create a free account. Then visit
https://archive.org/account/s3.php to get your **S3 access key** and **secret
key** — these are the upload credentials.

### 3. Install the project

```bash
git clone <this repo>
cd daf-yomi-podcast
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -e ".[dev]"
```

### 4. Configure credentials

Either run the interactive flow:

```bash
ia configure
```

…or copy `.env.example` to `.env` and fill in `IA_ACCESS_KEY` /
`IA_SECRET_KEY`. Also set `FEED_BASE_URL` and `COVER_ART_URL` in `.env` to the
public URLs where you'll host the feed and cover image.

### 5. Get a copy of the Drive folder locally

[`rclone`](https://rclone.org) is the easiest way:

```bash
rclone config             # set up "gdrive" remote
rclone copy gdrive:DafYomi ./drive-mirror --transfers=8 --progress
```

That's a one-time ~50–80 GB download.

## Recommended workflow for the bulk migration

```bash
# 1. Build the DB schema (idempotent).
dafyomi init-db

# 2. Scan the local mirror — populates the episode manifest.
dafyomi scan ./drive-mirror

# 3. Sanity-check progress.
dafyomi status

# 4. Test the audio pipeline on 5 episodes first.
dafyomi normalize --limit 5

# 5. Dry-run the IA upload to see what identifiers/URLs you'll get.
dafyomi upload --dry-run

# 6. Real upload of 5 test episodes; then go to archive.org and
#    confirm they look right.
dafyomi upload --limit 5

# 7. Once you're happy, run the rest of the pipeline.
dafyomi normalize     # all remaining
dafyomi upload        # all remaining

# 8. Build the feed.
dafyomi rss

# 9. Host feed.xml somewhere stable. Easiest: GitHub Pages.
#    Cloudflare Pages or any static host works equally well.

# 10. Switch your existing Spotify show over to RSS at
#     https://podcasters.spotify.com — "Switch hosting" flow,
#     paste the URL of feed.xml, confirm via the verification email.
#     Apple, Overcast, etc. pick up the same feed once you submit it
#     to https://podcastsconnect.apple.com.
```

After Spotify pulls the new feed, your existing 5 episodes there get replaced
by the full back-catalog from Internet Archive.

## How metadata flows into the feed

- **Show title / author / email / category** → `src/dafyomi/show_config.py`
- **Per-masechet Hebrew name and season number** → `src/dafyomi/seasons.py`
- **Episode title** → `<MasechetName> <DafNumber>` (e.g. `Berachot 47`)
- **Episode subtitle** → `<MasechetHe> <gematria>` (e.g. `ברכות מז`),
  computed by `src/dafyomi/gematria.py` with the daf-yomi convention that
  15 → טו and 16 → טז (never יה or יו, since those spell part of a divine name).
  This convention also applies to the trailing two digits of larger numbers
  (115 → קטו, 215 → רטו).
- **Episode description** — if a `<filename>.meta.txt` companion exists, its
  contents are used verbatim; otherwise a fallback line is generated.
- **`<pubDate>`** — pulled from the m4a's `creation_time` tag via mutagen, so
  episodes appear in chronological order in podcast apps.

## What's not yet here (Phase 2)

- **Google Drive watcher** — auto-detect new shiur uploads, run the pipeline,
  push the new episode to IA, and regenerate `feed.xml`. The current Phase 1
  is the bulk-migration tool; Phase 2 makes it a daily-shiur publisher.
- **Daily cron / GitHub Action** to run the watcher and re-publish the feed.
- **Cover art generation** — for now, you upload a static image and point
  `COVER_ART_URL` at it.
- **Web dashboard** — for now, `dafyomi status` is the only reporting.
- **Postgres deployment** — schema is Postgres-portable but we run on SQLite
  while the catalog lives on a single workstation.

## Project layout

```
daf-yomi-podcast/
├── src/dafyomi/
│   ├── cli.py            # `dafyomi <command>` entrypoints
│   ├── db.py             # SQLAlchemy engine + schema bootstrap
│   ├── models.py         # ORM models (mirror migrations/0001_init.sql)
│   ├── scan.py           # folder walk → DB
│   ├── gematria.py       # daf number → Hebrew letters (with 15/16 fix)
│   ├── seasons.py        # canonical Bavli order + fuzzy folder matching
│   ├── normalize.py      # ffmpeg loudnorm wrapper
│   ├── ia.py             # Internet Archive uploader
│   ├── rss.py            # RSS XML builder
│   ├── meta.py           # .meta.txt reader + fallback descriptions
│   └── show_config.py    # channel-level metadata
├── migrations/0001_init.sql
└── tests/
```

## Tests

```bash
pytest
```

The gematria tests are the most important — they assert exhaustively over
daf 2..200 that the result never contains יה or יו, and check known values
like Berachot 47 → מז, Bava Batra 176 → קעו.
