"""
One-off backfill (issue #11): probe Cover Art Archive for every existing
album that has an mbid, and store a Spotify fallback cover in
albums.spotify_cover_url wherever CAA doesn't have art. The ongoing
pipeline (album_push_logic.py) now does this automatically for *new*
albums as they're ingested; this script is just to backfill everything
that was already in the library before this feature existed.

Run locally once, after adding real spotify_id/spotify_key to your .env:
    python -m src.ingestion.backfill_cover_art

Takes a while — one Cover Art Archive request per album (~1,000+), with an
extra Spotify search only for the ones that 404. Safe to re-run: rows that
already have a spotify_cover_url are left untouched unless CAA has since
started 404ing where it didn't before (unlikely, but harmless to recheck).
"""

import os
import sys

from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.spotify_client import get_cover_art_fallback

load_dotenv()

url = os.environ.get("supabase_url")
key = os.environ.get("supabase_key")
supabase: Client = create_client(url, key)


def _artist_names(album_id: str) -> str:
    resp = (
        supabase.table("album_contributions")
        .select("artists(name)")
        .eq("album_id", album_id)
        .eq("role", "artist")
        .execute()
    )
    return ", ".join(
        c["artists"]["name"]
        for c in (resp.data or [])
        if c.get("artists") and c["artists"].get("name")
    )


def main():
    # Same pagination pattern as get_existing_album_ids() in
    # album_push_logic.py — PostgREST caps a single .select() at 1000 rows.
    PAGE_SIZE = 1000
    rows, start = [], 0
    while True:
        resp = (
            supabase.table("albums")
            .select("id, title, mbid")
            .not_.is_("mbid", "null")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    print(f"Probing Cover Art Archive for {len(rows)} album(s) with an mbid.")

    backfilled = 0
    for row in rows:
        artists = _artist_names(row["id"])
        try:
            fallback_url = get_cover_art_fallback(row["mbid"], row["title"], artists)
        except Exception as e:
            print(f"  error on {row['title']}: {e}")
            continue

        if fallback_url:
            supabase.table("albums").update({"spotify_cover_url": fallback_url}).eq("id", row["id"]).execute()
            print(f"  fallback set: {row['title']}")
            backfilled += 1

    print(f"\nDone. {backfilled}/{len(rows)} album(s) got a Spotify cover fallback.")


if __name__ == "__main__":
    main()
