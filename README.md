# Album Recommendations

![License](https://img.shields.io/badge/license-MIT-blue.svg)

A personal album-recommendation pipeline. It pulls my own rated album
library out of Notion, enriches each album with real metadata and tags from
MusicBrainz, stores everything in Supabase, and computes content-based
recommendations from the result. The public-facing app that actually
displays recommendations lives in the companion
[Album-Recommendations-Public](https://github.com/ChristianCrivelli/Album-Recommendations-Public)
repo (a Streamlit app deployed on Render) — this repo is the ingestion +
recommendation backend that feeds it.

## How it fits together

```
Notion (my rated album library)
        │
        ▼
src/ingestion/pull_albums.py       — pulls the full, paginated Notion database
        │
        ▼
src/ingestion/album_push_logic.py  — delta-pull: only new/changed albums go on
        │                              to MusicBrainz; existing ones just get a
        │                              rating/timestamp refresh
        ▼
src/ingestion/album_finder.py      — looks up each new album on MusicBrainz
        │                             (exact title + artist match only — no
        │                             fuzzy guessing), pulling genre/style tags,
        │                             release year, track length, and artist +
        │                             producer credits
        ▼
Supabase (albums, artists, tags, album_contributions, album_tags)
        │
        ▼
src/recommendations/similiarity_matrix.py  — builds a weighted feature matrix
        │                                     (tags, shared artists/producers,
        │                                     release year, track length)
        ▼
src/recommendations/recommender.py — cosine similarity → "if you liked X, try Y"
```

Anything MusicBrainz can't confidently match (ambiguous title, artist not
indexed, obvious data-entry typo) is logged to `failed_lookups` instead of
guessed at, and can be corrected without touching Notion via a
`manual_overrides` row — either a search hint (tell it what to actually
search for) or a fully manual entry (skip MusicBrainz for this title
entirely). See `config/manual_override_examples.sql` for both modes
in practice, and `config/schema.sql` for the full table layout.

## Running it

**Requirements:** Python 3.11+, a Supabase project (see
`config/schema.sql` for the schema), a Notion database of rated
albums, and a MusicBrainz-friendly contact email (MusicBrainz's API asks for
one in the user agent).

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in the values below
python -m src.ingestion.album_push_logic
```

| Variable | What it's for |
|---|---|
| `notion_key`, `database_id` | Notion integration token + the album database's ID |
| `supabase_url`, `supabase_key` | Supabase project connection |
| `email` | Contact email sent in MusicBrainz's required user-agent string |
| `spotify_key`, `spotify_id` | Spotify Client Credentials (`spotify_id` = Client ID, `spotify_key` = Client Secret) — used by `src/ingestion/spotify_client.py` as a fallback when MusicBrainz has no match, for a Cover Art Archive cover-art fallback, and to resolve the Spotify album ID the public webapp embeds for in-app previews (issue #11). Optional: every function in that module degrades to `None` if these aren't set, so the pipeline still runs fine without them — just without the fallback. Get these from your own app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard). |

By default this runs a **delta pull**: only albums that aren't already in
Supabase get looked up on MusicBrainz; everything else just gets its rating
and Notion timestamps refreshed. Set `FULL_SYNC=true` to force a full
rebuild of every album's metadata instead — this is slow (MusicBrainz allows
1 request/second, and each album takes 2-3 calls) and, on a library this
size, can take several hours, so it's not something to run casually. See
`.github/workflows/deep_sync.yml` for how the monthly full sync splits the
work across parallel shards to stay under GitHub Actions' job time limit.

To build the recommendation feature matrix once the database is populated:

```bash
python -m src.recommendations.similiarity_matrix
```

**One-off backfills** (issue #11 — run once locally after adding Spotify
credentials; the regular pipeline handles new albums automatically going
forward):

```bash
python -m src.ingestion.backfill_spotify_metadata  # resolve the existing MusicBrainz-miss backlog via Spotify
python -m src.ingestion.backfill_cover_art         # probe Cover Art Archive and backfill Spotify covers where it 404s
```

## Automation

- **`.github/workflows/daily_pipeline.yml`** — runs the delta pull nightly.
- **`.github/workflows/deep_sync.yml`** — runs a full `FULL_SYNC=true`
  rebuild monthly (or on demand via workflow_dispatch), sharded across 4
  parallel jobs.

Both read Notion/Supabase/MusicBrainz credentials from GitHub Actions
secrets — see the `env:` block in either workflow file for the exact secret
names to configure in the repo settings.
