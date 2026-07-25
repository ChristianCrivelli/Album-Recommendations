import os
import sys
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.pull_albums import fetch_notion_dataframe
from ingestion.album_finder import get_metadata, get_producers
from ingestion.cleaning_methods import clean_artist_list, clean_and_normalize_tags
from ingestion.bad_eggs import record_bad_egg as _record_bad_egg, clear_bad_eggs as _clear_bad_eggs


load_dotenv()

url = os.environ.get("supabase_url")
key = os.environ.get("supabase_key")

supabase: Client = create_client(url, key)

# FULL_SYNC=true forces a ground-up rebuild (used by the monthly deep sync).
# Otherwise this is a delta pull: only new albums hit MusicBrainz/Spotify.
FULL_SYNC = os.getenv("FULL_SYNC", "false").strip().lower() == "true"


def get_existing_titles() -> set:
    resp = supabase.table("albums").select("title").execute()
    return {row["title"].strip().lower() for row in resp.data if row.get("title")}


# Thin wrappers binding the shared helpers to this script's supabase client,
# so the call sites below don't change.
def record_bad_egg(title: str, artists: str, reason: str) -> None:
    _record_bad_egg(supabase, title, artists, reason)


def clear_bad_eggs(title: str) -> None:
    _clear_bad_eggs(supabase, title)


# === Get the Data From Notion ===
df = fetch_notion_dataframe()
df = df[['Title', 'Artist(s)', 'Rating/10', 'NotionCreatedAt', 'NotionEditedAt']]
df = df.rename(columns={'Artist(s)': 'Artists', 'Rating/10': 'Rating'})

# Strip stray whitespace from titles at ingestion time. Untrimmed titles used
# to slip into Supabase, and since /api/recommend strips the incoming search
# query but compares it against the stored title, a title like "Temporary "
# would show up fine in autocomplete but never match on search.
df['Title'] = df['Title'].astype(str).str.strip()

# Clean the entire Artists column before looping
df['Artists'] = df['Artists'].apply(clean_artist_list)

print(f"Loaded {len(df)} albums from Notion.")

# === Delta pull: skip MusicBrainz/Spotify calls for albums we already have ===
if FULL_SYNC:
    print("FULL_SYNC enabled — rebuilding metadata for every album.")
else:
    existing_titles = get_existing_titles()
    is_new = ~df['Title'].str.strip().str.lower().isin(existing_titles)

    # Existing albums skip enrichment entirely, but keep their rating and
    # Notion timestamps fresh — rating and last_edited_time are the two
    # things that change in Notion after the fact. Sending notion_created_at
    # here too (harmless — it never actually changes) is what backfills it
    # onto any album row that existed before this feature, automatically,
    # on the very next run — no separate migration/backfill script needed.
    for row in df[~is_new].itertuples():
        supabase.table("albums").update({
            "rating": row.Rating,
            "notion_created_at": row.NotionCreatedAt,
            "notion_edited_at": row.NotionEditedAt,
        }).eq("title", row.Title).execute()

    skipped = len(df) - is_new.sum()
    df = df[is_new]
    print(f"Delta pull: {len(df)} new album(s) to enrich, {skipped} already synced (rating refreshed).")

# Tip 3: track failures so we can save them at the end
failures = []

# === Loop through the table from Notion to enrich it with Musicbrainz Data ===
n = 1
for row in df.itertuples():
    print(f"--- Processing N.{n}: {row.Title} ---")
    n += 1

    # 1. Get metadata
    search_artist = ", ".join(row.Artists)
    meta = get_metadata(row.Title, search_artist)

    # 2. Insert/Get Artist ID
    if meta and meta.get('Release ID'): 
        release_id = meta['Release ID']

        # Entity A (Album)
        album_data = {
            "title": row.Title,
            "mbid": release_id,
            "rating": row.Rating,
            "primary_type": meta.get('Primary Type'),
            "release_year": meta.get('Release Year'),
            "avg_length": meta.get('Avg Track Length (Mins)'),
            "notion_created_at": row.NotionCreatedAt,
            "notion_edited_at": row.NotionEditedAt,
        }

        # Entities B & C (Contributors)
        producers = get_producers(release_id)
        contributors = []
        
        for artist in meta.get('Artists', []):
            contributors.append({
                'name': artist['name'],
                'mbid': artist['mbid'],
                'role': 'artist'
            })

        for prod in producers:
            contributors.append({
                'name': prod['name'],
                'mbid': prod['mbid'],
                'role': 'producer'
            })
        
        # Push into Supabase
        try:
            # Upsert Album
            album_resp = supabase.table("albums").upsert(
                album_data, 
                on_conflict="mbid"
            ).execute()
            
            # Ensure we got data back before extracting the UUID
            if not album_resp.data:
                print(f"Warning: No data returned from Supabase for {row.Title}. Check RLS policies.")
                reason = "Supabase returned no data"
                failures.append({"title": row.Title, "artists": search_artist, "reason": reason})
                record_bad_egg(title=row.Title, artists=search_artist, reason=reason)
                continue
                
            album_db_id = album_resp.data[0]['id']

            # This title now has a real album row, so any bad-egg flags left
            # over from a previous run (e.g. an old "MusicBrainz lookup
            # failed") are stale. Clear them first — anything still wrong
            # this run (e.g. a missing-mbid contributor below) gets re-flagged.
            clear_bad_eggs(row.Title)

            # Loop through all contributors
            for person in contributors:
                if person.get('mbid'):
                    person_resp = supabase.table("artists").upsert(
                        {"name": person['name'], "mbid": person['mbid']}, 
                        on_conflict="mbid"
                    ).execute()
                    person_db_id = person_resp.data[0]['id'] if person_resp.data else None
                else:
                    # No mbid from MusicBrainz for this contributor. Previously this
                    # branch just skipped the person entirely, which is why some
                    # albums end up showing "Unknown artist" downstream: no row in
                    # artists, no link in album_contributions, nothing for the API
                    # to display. Instead, link by name (find-or-create) so the
                    # album still has a real artist attached, and flag it as a bad
                    # egg since a name-only match could collide with a different
                    # artist of the same name and deserves a manual look.
                    existing = (
                        supabase.table("artists")
                        .select("id")
                        .eq("name", person['name'])
                        .limit(1)
                        .execute()
                    )
                    if existing.data:
                        person_db_id = existing.data[0]['id']
                    else:
                        created = supabase.table("artists").insert(
                            {"name": person['name']}
                        ).execute()
                        person_db_id = created.data[0]['id'] if created.data else None

                    record_bad_egg(
                        title=row.Title,
                        artists=search_artist,
                        reason=f"No MusicBrainz mbid for contributor '{person['name']}' ({person['role']}) — linked by name only, verify for duplicate artist rows.",
                    )

                if person_db_id:
                    # Step 3: Create the link in the Junction Table
                    link_data = {
                        "album_id": album_db_id,
                        "person_id": person_db_id,
                        "role": person['role']
                    }

                    supabase.table("album_contributions").upsert(
                        link_data,
                        on_conflict="album_id,person_id,role"
                    ).execute()
            
            # Loop through all tags
            raw_tags = meta.get('Top Tags', [])

            top_tags = clean_and_normalize_tags(raw_tags)

            if not top_tags:
                record_bad_egg(
                    title=row.Title,
                    artists=search_artist,
                    reason="No tags found from MusicBrainz release-group or artist fallback — needs a manual tag override.",
                )

            for tag_name in top_tags:
                # Upsert the tag into a 'tags' table
                tag_resp = supabase.table("tags").upsert(
                    {"name": tag_name}, 
                    on_conflict="name" # Assumes 'name' is unique in your tags table
                ).execute()
                
                if tag_resp.data:
                    tag_db_id = tag_resp.data[0]['id']
                    
                    # Create the link in the Tag Junction Table
                    tag_link_data = {
                        "album_id": album_db_id,
                        "tag_id": tag_db_id
                    }
                    
                    supabase.table("album_tags").upsert(
                        tag_link_data, 
                        on_conflict="album_id,tag_id"
                    ).execute()

            print(f"Success! Added {len(contributors)} contributors and {len(top_tags)} tags.")
            
        except Exception as e:
            print(f"Database error for {row.Title}: {e}")
            reason = f"DB error: {e}"
            failures.append({"title": row.Title, "artists": search_artist, "reason": reason})
            record_bad_egg(title=row.Title, artists=search_artist, reason=reason)

    else:
        print(f"Could not find MusicBrainz data for {row.Title}")
        # Tip 3: record the failure with a reason so it's easy to investigate
        reason = "MusicBrainz lookup failed"
        failures.append({"title": row.Title, "artists": search_artist, "reason": reason})
        record_bad_egg(title=row.Title, artists=search_artist, reason=reason)

# Tip 3: the CSV is kept as a local run artifact for convenience, but it lives
# on the GitHub Actions runner's disk and is destroyed when the job ends —
# it's not actually a durable record. The Supabase failed_lookups table
# (populated via record_bad_egg above, as failures happen) is now the source
# of truth Chris can check any time: `SELECT * FROM open_bad_eggs;`
if failures:
    failures_df = pd.DataFrame(failures)
    failures_df.to_csv("failed_lookups.csv", index=False)
    print(f"\nDone! {len(failures)} album(s) failed — saved to Supabase failed_lookups table (and failed_lookups.csv locally).")
else:
    print("\nDone! All albums processed successfully.")