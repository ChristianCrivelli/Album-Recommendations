"""
Manual metadata overrides for albums the automated MusicBrainz pipeline
can't resolve on its own — see config/manual_override_examples.sql
for the table this reads from and the two override modes it supports
(search-hint vs. full-manual).

Split out into its own module for the same reason as bad_eggs.py: keep it
importable without triggering album_push_logic.py's top-level Notion pull.
"""


def _normalize(name):
    """Case/whitespace-insensitive normalization, matching the same
    exact-but-not-fuzzy approach as album_finder.py's artist matching."""
    return " ".join((name or "").strip().lower().split())


def get_override(supabase, title: str, artist: str = None):
    """Returns the manual_overrides row for this title, or None if there
    isn't one.

    Title alone stopped being a safe lookup key once the albums.title
    unique constraint was dropped (issue #14: two different real albums can
    legitimately share an exact title — confirmed cases include "The Purple
    Album" and "Welcome to the Future"). So this now handles the case where
    more than one manual_overrides row shares a title: if there's exactly
    one match, it's returned as before (the overwhelming majority of rows —
    no title collision exists for them, so `artist` is never even
    consulted). If there's more than one, `artist` (the same comma-joined
    string used everywhere else in the pipeline, e.g. album_push_logic.py's
    search_artist) is used to pick the right one; if none matches, falls
    back to the first row rather than dropping the album entirely.

    Never raises — a lookup failure here just falls back to normal (no
    override) behavior rather than taking down the album."""
    try:
        resp = supabase.table("manual_overrides").select("*").eq("title", title).execute()
        rows = resp.data or []
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]

        if artist:
            wanted = _normalize(artist)
            for row in rows:
                if _normalize(row.get("artist")) == wanted:
                    return row
        print(
            f"Warning: {len(rows)} manual_overrides rows share title '{title}' and "
            f"none matched artist '{artist}' — using the first row. Set `artist` on "
            f"the intended row to disambiguate (see config/queries/"
            f"title_uniqueness_migration.sql)."
        )
        return rows[0]
    except Exception as e:
        print(f"Warning: could not check manual_overrides for {title} / {artist}: {e}")
        return None
