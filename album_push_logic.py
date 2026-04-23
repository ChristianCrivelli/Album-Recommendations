import os
import time
import pandas as pd
from album_finder import get_metadata, get_producers
from pull_albums import fetch_notion_dataframe
from cleaning_methods import clean_artist_list
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)

# === Get the Data From Notion ===
df = fetch_notion_dataframe()
df = df[['Title', 'Artist(s)', 'Rating/10']]
df = df.rename(columns={'Artist(s)': 'Artists', 'Rating/10': 'Rating'})

# Clean the entire Artists column before looping
df['Artists'] = df['Artists'].apply(clean_artist_list)

print(f"Loaded {len(df)} albums from Notion.")

# === Loop through the table from Notion to enrich it with Musicbrainz Data ===
for row in df.itertuples():
    print(f"--- Processing: {row.Title} ---")

    # 1. Get metadata
    search_artist = ", ".join(row.Artists)
    meta = get_metadata(row.Title, search_artist)

    # 2. Insert/Get Artist ID
    if meta and meta.get('release_id'):
        release_id = meta['release_id']

        # Entity A (Album)
        album_data = {
            "title": row.Title,
            "mbid": release_id,
            "rating": row.Rating,
            "primary_type": meta.get('primary_type'),
            "release_year": meta.get('release_year'),
            "top_tags": meta.get('top_tags'), 
            "avg_length": meta.get('avg_length'),
        }

        # Entities B & C (Contributors)
        producers = get_producers(release_id)
        contributors = []
        
        for artist in meta.get('artists', []):
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
            # Step 1: Upsert Album
            album_resp = supabase.table("albums").upsert(
                album_data, 
                on_conflict="mbid"
            ).execute()
            
            # Ensure we got data back before extracting the UUID
            if not album_resp.data:
                print(f"Warning: No data returned from Supabase for {row.Title}. Check RLS policies.")
                continue
                
            album_db_id = album_resp.data[0]['id']
            
            # Step 2: Loop through all contributors
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
            
            print(f"Success! Added {len(contributors)} contributors.")
            
        except Exception as e:
            print(f"Database error for {row.Title}: {e}")

    else:
        print(f"Could not find MusicBrainz data for {row.Title}")

    time.sleep(1.5) # Sleep to respect rate limits

print("Done!")