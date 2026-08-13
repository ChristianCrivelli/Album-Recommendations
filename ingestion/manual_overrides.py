"""
Manual metadata overrides for albums the automated MusicBrainz pipeline
can't resolve on its own — see database_info/migrations/manual_overrides.sql
for the table this reads from and the two override modes it supports
(search-hint vs. full-manual).

Split out into its own module for the same reason as bad_eggs.py: keep it
importable without triggering album_push_logic.py's top-level Notion pull.
"""


def get_override(supabase, title: str):
    """Returns the manual_overrides row for this exact title, or None if
    there isn't one. Never raises — a lookup failure here just falls back
    to normal (no override) behavior rather than taking down the album."""
    try:
        resp = (
            supabase.table("manual_overrides")
            .select("*")
            .eq("title", title)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"Warning: could not check manual_overrides for {title}: {e}")
        return None