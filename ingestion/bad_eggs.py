"""
Shared helpers for recording "bad eggs" — anything the pipeline couldn't
fully resolve — to the Supabase failed_lookups table, so they survive past
the GitHub Actions runner being torn down at the end of each job.

Split out into its own module so scripts like backfill_tags.py can reuse
these without importing album_push_logic.py, which runs its Notion pull as
top-level module code the moment it's imported.
"""


def record_bad_egg(supabase, title: str, artists: str, reason: str) -> None:
    try:
        supabase.table("failed_lookups").upsert(
            {"title": title, "artists": artists, "reason": reason, "resolved": False},
            on_conflict="title,reason",
        ).execute()
    except Exception as e:
        # Never let bad-egg bookkeeping itself take down the pipeline
        print(f"Warning: could not record bad egg for {title}: {e}")


def clear_bad_eggs(supabase, title: str) -> None:
    """Once an album fully succeeds, drop any previously recorded bad-egg
    rows for it so the open_bad_eggs view stays a true 'still needs attention' list."""
    try:
        supabase.table("failed_lookups").delete().eq("title", title).execute()
    except Exception as e:
        print(f"Warning: could not clear bad eggs for {title}: {e}")