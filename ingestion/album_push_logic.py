import os
import sys
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.pull_albums import fetch_notion_dataframe
from ingestion.album_finder import get_metadata, get_producers
from ingestion.cleaning_methods import clean_artist_list, clean_and_normalize_tags


load_dotenv()

url = os.environ.get("supabase_url")
key = os.environ.get("supabase_key")

supabase: Client = create_client(url, key)

# === Get the Data From Notion ===
df = fetch_notion_dataframe()
df = df[['Title', 'Artist(s)', 'Rating/10']]
df = df.rename(columns={'Artist(s)': 'Artists', 'Rating/10': 'Rating'})

# Clean the entire Artists column before looping
df['Artists'] = df['Artists'].apply(clean_artist_list)

print(f"Loaded {len(df)} albums from Notion.")

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
                failures.append({"title": row.Title, "artists": search_artist, "reason": "Supabase returned no data"})
                continue
                
            album_db_id = album_resp.data[0]['id']
            
            # Loop through all contributors
            for person in contributors:
                if person.get('mbid'):
                    person_resp = supabase.table("artists").upsert(
                        {"name": person['name'], "mbid": person['mbid']}, 
                        on_conflict="mbid"
                    ).execute()
                    
                    if person_resp.data:
                        person_db_id = person_resp.data[0]['id']
                        
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
            failures.append({"title": row.Title, "artists": search_artist, "reason": f"DB error: {e}"})

    else:
        print(f"Could not find MusicBrainz data for {row.Title}")
        # Tip 3: record the failure with a reason so it's easy to investigate
        failures.append({"title": row.Title, "artists": search_artist, "reason": "MusicBrainz lookup failed"})

# Tip 3: write all failures to a CSV after the run completes
if failures:
    failures_df = pd.DataFrame(failures)
    failures_df.to_csv("failed_lookups.csv", index=False)
    print(f"\nDone! {len(failures)} album(s) failed — saved to failed_lookups.csv")
else:
    print("\nDone! All albums processed successfully.")