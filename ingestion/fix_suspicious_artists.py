"""
One-off remediation for the 2026-08 retroactive artist-mismatch audit
(see claude/artist-mismatch-audit-2026-08-18.md in the Album-Recommendations
Claude Project). That audit compared every Notion row's Artist(s) against the
artist already linked to the same-titled album in Supabase and found 113
albums where the two disagree in a way that isn't explained by a known
alias/spelling variant — i.e. Supabase is very likely showing the wrong
artist for these 113 albums.

This script re-attempts each of those 113 albums against MusicBrainz using
the now-exact title+artist matching in ingestion/album_finder.py (see that
file's history: title matching used to be fuzzy, which combined with
already-exact artist matching still let wrong-album matches through
undetected — this audit is why it was tightened).

For each of the 113 albums, by title:
  - If MusicBrainz has a release-group with an EXACT title match AND an
    EXACT artist match for the Notion artist: correct the Supabase album row
    (mbid/primary_type/release_year/avg_length), replace its artist/producer
    contributions and tags with the freshly matched data, and clear it from
    failed_lookups.
  - If MusicBrainz has no such exact match: the artist link we currently
    have is already confirmed wrong (that's why the album is in this list),
    so leaving it in place would keep showing incorrect data. Clear the
    album's mbid/primary_type/release_year/avg_length, remove its artist and
    producer contribution links and tags (all of which came from the same
    wrong MusicBrainz match), and record it in failed_lookups for manual
    review. Title and rating (the two pieces of data that are independently
    known-good — they come straight from Notion) are left untouched in both
    branches.

This is a one-off script, not part of the regular pipeline. Meant to be run
once via the "Fix Suspicious Artist Matches" GitHub Actions workflow
(workflow_dispatch), which has network access to MusicBrainz and the
Supabase secrets already configured for deep_sync.yml.
"""
import json
import os
import sys

from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.album_finder import get_metadata, get_producers
from ingestion.cleaning_methods import clean_and_normalize_tags
from ingestion.bad_eggs import record_bad_egg as _record_bad_egg, clear_bad_eggs as _clear_bad_eggs

load_dotenv()

url = os.environ.get("supabase_url")
key = os.environ.get("supabase_key")
supabase: Client = create_client(url, key)


def record_bad_egg(title, artists, reason):
    _record_bad_egg(supabase, title, artists, reason)


def clear_bad_eggs(title):
    _clear_bad_eggs(supabase, title)


HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "data", "suspicious_wrong_artist_matches.json")) as f:
    SUSPICIOUS = json.load(f)

print(f"Loaded {len(SUSPICIOUS)} suspicious wrong-artist album(s) to re-check.")

fixed = []
flagged = []
skipped = []

for i, item in enumerate(SUSPICIOUS, 1):
    title = item["title"]
    notion_artist = item["notion_artist"]
    supabase_artist = item["supabase_artist"]
    print(f"\n--- [{i}/{len(SUSPICIOUS)}] {title!r} (Notion: {notion_artist!r}, currently linked: {supabase_artist!r}) ---")

    # Find the existing album row. Titles were matched exactly between
    # Notion and Supabase by the audit that produced this list, but fall
    # back to a case-insensitive lookup just in case.
    existing = supabase.table("albums").select("id, title, mbid").eq("title", title).limit(1).execute()
    if not existing.data:
        existing = supabase.table("albums").select("id, title, mbid").ilike("title", title).limit(1).execute()
    if not existing.data:
        print(f"  SKIP: no album row found in Supabase for title {title!r} — may have been renamed/removed since the audit.")
        skipped.append({"title": title, "reason": "album row not found"})
        continue

    album_db_id = existing.data[0]["id"]
    old_mbid = existing.data[0]["mbid"]

    try:
        meta, mb_reason = get_metadata(title, notion_artist)
    except Exception as e:
        print(f"  ERROR calling MusicBrainz for {title!r}: {e}")
        skipped.append({"title": title, "reason": f"MusicBrainz call raised: {e}"})
        continue

    if meta and meta.get("Release ID"):
        release_id = meta["Release ID"]

        album_update = {
            "mbid": meta.get("Release Group ID"),
            "primary_type": meta.get("Primary Type"),
            "release_year": meta.get("Release Year"),
            "avg_length": meta.get("Avg Track Length (Mins)"),
        }

        try:
            supabase.table("albums").update(album_update).eq("id", album_db_id).execute()
        except Exception as e:
            # Most likely cause: the new mbid collides with a DIFFERENT
            # album row already in Supabase (e.g. this exact release was
            # already correctly ingested under another title/casing) —
            # unique constraint on albums.mbid. Don't guess further; flag it.
            print(f"  ERROR updating album row for {title!r} (likely mbid collision with another row): {e}")
            reason = f"MusicBrainz match found ({meta.get('Release Group ID')}) but updating Supabase failed: {e}"
            record_bad_egg(title=title, artists=notion_artist, reason=reason)
            flagged.append({"title": title, "reason": reason})
            continue

        # The old contributor/tag links were built from the WRONG
        # release-group's data — wipe them before adding the correct ones,
        # rather than leaving stale wrong-artist/wrong-tag links sitting
        # alongside the new correct ones.
        supabase.table("album_contributions").delete().eq("album_id", album_db_id).execute()
        supabase.table("album_tags").delete().eq("album_id", album_db_id).execute()

        try:
            producers = get_producers(release_id)
        except Exception as e:
            print(f"  Warning: producer lookup failed for {title!r}: {e}")
            producers = []

        contributors = []
        for artist in meta.get("Artists", []):
            contributors.append({"name": artist["name"], "mbid": artist["mbid"], "role": "artist"})
        for prod in producers:
            contributors.append({"name": prod["name"], "mbid": prod["mbid"], "role": "producer"})

        for person in contributors:
            if person.get("mbid"):
                person_resp = supabase.table("artists").upsert(
                    {"name": person["name"], "mbid": person["mbid"]},
                    on_conflict="mbid",
                ).execute()
                person_db_id = person_resp.data[0]["id"] if person_resp.data else None
            else:
                existing_artist = supabase.table("artists").select("id").eq("name", person["name"]).limit(1).execute()
                if existing_artist.data:
                    person_db_id = existing_artist.data[0]["id"]
                else:
                    created = supabase.table("artists").insert({"name": person["name"]}).execute()
                    person_db_id = created.data[0]["id"] if created.data else None
                record_bad_egg(
                    title=title,
                    artists=notion_artist,
                    reason=f"No MusicBrainz mbid for contributor '{person['name']}' ({person['role']}) — linked by name only, verify for duplicate artist rows.",
                )

            if person_db_id:
                supabase.table("album_contributions").upsert(
                    {"album_id": album_db_id, "person_id": person_db_id, "role": person["role"]},
                    on_conflict="album_id,person_id,role",
                ).execute()

        top_tags = clean_and_normalize_tags(meta.get("Top Tags", []))
        for tag_name in top_tags:
            tag_resp = supabase.table("tags").upsert({"name": tag_name}, on_conflict="name").execute()
            if tag_resp.data:
                tag_db_id = tag_resp.data[0]["id"]
                supabase.table("album_tags").upsert(
                    {"album_id": album_db_id, "tag_id": tag_db_id},
                    on_conflict="album_id,tag_id",
                ).execute()

        clear_bad_eggs(title)
        artist_names = ", ".join(a["name"] for a in meta.get("Artists", []))
        print(f"  FIXED: {title!r} now correctly linked to {artist_names!r} (mbid {meta.get('Release Group ID')}), {len(contributors)} contributor(s), {len(top_tags)} tag(s).")
        fixed.append({"title": title, "old_artist": supabase_artist, "new_artist": artist_names, "mbid": meta.get("Release Group ID")})

    else:
        # No exact title+artist match on MusicBrainz. We already know the
        # currently-linked artist is wrong (that's why this title is in the
        # suspicious list) — clear the wrong data rather than leave it
        # displayed, and flag for manual review.
        supabase.table("albums").update({
            "mbid": None,
            "primary_type": None,
            "release_year": None,
            "avg_length": None,
        }).eq("id", album_db_id).execute()
        supabase.table("album_contributions").delete().eq("album_id", album_db_id).execute()
        supabase.table("album_tags").delete().eq("album_id", album_db_id).execute()

        reason = (
            f"Retroactive audit flagged this as a wrong-artist match (was linked to "
            f"'{supabase_artist}', Notion says '{notion_artist}'). Re-checked with exact "
            f"title+artist matching: {mb_reason} Cleared the wrong mbid/type/year/length/"
            f"contributors/tags — needs a manual_overrides search_title/search_artist hint "
            f"or manual MBID."
        )
        record_bad_egg(title=title, artists=notion_artist, reason=reason)
        print(f"  FLAGGED: {title!r} — {mb_reason}")
        flagged.append({"title": title, "reason": mb_reason})

print("\n\n=== SUMMARY ===")
print(f"Fixed (exact match found, Supabase corrected): {len(fixed)}")
print(f"Flagged for manual review (no exact match, wrong data cleared): {len(flagged)}")
print(f"Skipped (couldn't process): {len(skipped)}")

if fixed:
    print("\n-- Fixed --")
    for f in fixed:
        print(f"  {f['title']!r}: {f['old_artist']!r} -> {f['new_artist']!r}")

if flagged:
    print("\n-- Flagged for manual review --")
    for f in flagged:
        print(f"  {f['title']!r}: {f['reason']}")

if skipped:
    print("\n-- Skipped --")
    for s in skipped:
        print(f"  {s['title']!r}: {s['reason']}")
