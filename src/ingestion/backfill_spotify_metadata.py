"""
One-off backfill (issue #11): try Spotify for every title currently stuck
on a MusicBrainz miss in failed_lookups ("No MusicBrainz candidate..." /
"No confident MusicBrainz match..."). As of 2026-08-29 that's ~311 distinct
titles — the ongoing pipeline (album_push_logic.py) now tries this
automatically for *new* misses going forward; this script is just to clear
the existing backlog in one pass.

Run locally once, after adding real spotify_id/spotify_key to your .env:
    python -m src.ingestion.backfill_spotify_metadata

Safe to re-run — anything Spotify still can't find is left as a bad egg,
untouched, for the next attempt (e.g. after a manual title fix).
"""

import os
import sys

from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.spotify_client import apply_spotify_fallback
from ingestion.bad_eggs import record_bad_egg as _record_bad_egg, clear_bad_eggs as _clear_bad_eggs

load_dotenv()

url = os.environ.get("supabase_url")
key = os.environ.get("supabase_key")
supabase: Client = create_client(url, key)


def main():
    stuck = (
        supabase.table("failed_lookups")
        .select("title, artists")
        .or_(
            "reason.ilike.no musicbrainz candidate%,"
            "reason.ilike.no confident musicbrainz match%"
        )
        .execute()
        .data
        or []
    )

    # De-dupe by title — bad_eggs.py upserts on (title, reason), so a title
    # that hit more than one of these two reason strings over time can show
    # up here twice.
    by_title = {row["title"]: row.get("artists") for row in stuck if row.get("title")}
    print(f"{len(by_title)} title(s) stuck on a MusicBrainz miss — trying Spotify for each.")

    resolved, resolved_untagged, still_stuck = 0, 0, 0
    for title, artists_str in by_title.items():
        artist_list = [a.strip() for a in (artists_str or "").split(",") if a.strip()]
        try:
            result = apply_spotify_fallback(supabase, title, artist_list)
        except Exception as e:
            print(f"  error on {title}: {e}")
            result = {"resolved": False, "tagged": False}

        if result["resolved"]:
            _clear_bad_eggs(supabase, title)
            if not result["tagged"]:
                _record_bad_egg(
                    supabase,
                    title,
                    artists_str,
                    "Resolved via Spotify fallback (no MusicBrainz match) — no tags available (Spotify had no artist genres either), needs a manual tag override if desired.",
                )
                resolved_untagged += 1
            print(f"  resolved{'' if result['tagged'] else ' (untagged)'}: {title}")
            resolved += 1
        else:
            print(f"  still nothing: {title}")
            still_stuck += 1

    print(
        f"\nDone. {resolved} resolved via Spotify ({resolved - resolved_untagged} with tags, "
        f"{resolved_untagged} still untagged), {still_stuck} still need a manual look."
    )


if __name__ == "__main__":
    main()
